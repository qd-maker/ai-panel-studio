import type { CSSProperties } from 'react'
import type { DiscussionDetail, Participant } from '../types'
import InsightBoard from './InsightBoard'
import './SummaryView.css'

interface Props {
  discussion: DiscussionDetail
  /** 讨论正在总结中（summary 还没到） */
  pending?: boolean
}

/** 兜底防线：后端保证 summary 是纯文本；万一收到 JSON 形态的字符串，界面不渲染原文 */
const looksLikeJson = (s: string) => /^\s*[[{]/.test(s) || /```/.test(s)

/** 统计值拆成「数字 + 单位」：数字用等宽字体，单位用正文字体 */
type Piece = [number | string, string]

function durationPieces(start: string | null, end: string | null): Piece[] {
  if (!start || !end) return [['—', '']]
  const sec = Math.max(0, Math.round((Date.parse(end) - Date.parse(start)) / 1000))
  const m = Math.floor(sec / 60)
  return m > 0 ? [[m, '分'], [String(sec % 60).padStart(2, '0'), '秒']] : [[sec, '秒']]
}

export default function SummaryView({ discussion: d, pending = false }: Props) {
  const host = d.participants.find((p) => p.role === 'host')
  const experts = d.participants.filter((p) => p.role === 'expert').sort((a, b) => a.seat_no - b.seat_no)
  const paragraphs =
    d.summary && !looksLikeJson(d.summary) ? d.summary.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean) : []

  const countBy = new Map<string, number>()
  d.utterances.forEach((u) => countBy.set(u.participant_id, (countBy.get(u.participant_id) ?? 0) + 1))
  const stateBy = new Map(d.agent_states.map((s) => [s.participant_id, s]))
  // 最终立场：取小窗最后一次的公开思考摘要（观点本身）；没有时回退到阵容里的立场
  const finalView = (p: Participant) => stateBy.get(p.id)?.public_thought || p.stance

  const finalInsights = d.insights.filter((i) => i.status !== 'dropped')
  const stats: { label: string; value: Piece[] }[] = [
    { label: '时长', value: durationPieces(d.started_at, d.ended_at) },
    { label: '发言', value: [[d.utterances.length, '条']] },
    { label: '专家发言', value: [[d.expert_turns, '轮']] },
    { label: '共识', value: [[finalInsights.filter((i) => i.kind === 'consensus').length, '条']] },
    { label: '分歧', value: [[finalInsights.filter((i) => i.kind === 'divergence').length, '条']] },
  ]

  return (
    <article className="summary scroll-y" aria-label="本场总结">
      <div className="summary-inner">
        <header className="summary-head">
          <p className="eyebrow">本场总结</p>
          <h1 className="summary-topic">{d.topic}</h1>
          <dl className="summary-stats">
            {stats.map((s) => (
              <div key={s.label}>
                <dt>{s.label}</dt>
                <dd>
                  {s.value.map(([n, unit], i) => (
                    <span key={i}>
                      <b>{n}</b>
                      {unit && <small>{unit}</small>}
                    </span>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </header>

        <div className="summary-grid">
          <div className="summary-main">
            <section className="summary-text" aria-label="主持人总结">
              {paragraphs.length > 0 ? (
                <>
                  {paragraphs.map((p, i) => (
                    <p key={i} className={i === 0 ? 'summary-p dropcap' : 'summary-p'}>
                      {p}
                    </p>
                  ))}
                  <footer className="summary-sign" style={{ '--c': host?.color } as CSSProperties}>
                    {host && <span className="avatar avatar-sm">{host.name.slice(0, 1)}</span>}
                    <span>主持人 {host?.name}</span>
                    {d.summary_source === 'fallback' && <span className="summary-note">根据讨论中的共识与分歧整理</span>}
                  </footer>
                </>
              ) : pending ? (
                <div className="summary-pending" aria-busy="true">
                  <p>主持人正在整理本场总结⋯⋯</p>
                  <span className="summary-line" />
                  <span className="summary-line" />
                  <span className="summary-line short" />
                </div>
              ) : (
                <p className="summary-empty">{d.summary ? '总结暂时无法显示，请稍后刷新。' : '讨论结束后，主持人会在这里做总结。'}</p>
              )}
            </section>

            <section className="summary-section" aria-label="嘉宾最终立场">
              <h2 className="summary-h2">嘉宾最终立场</h2>
              <ul className="stance-list">
                {experts.map((p) => (
                  <li key={p.id} className="stance-item" style={{ '--c': p.color } as CSSProperties}>
                    <span className="avatar">{p.name.slice(0, 1)}</span>
                    <div className="stance-body">
                      <p className="stance-who">
                        <span className="guest-name-c">{p.name}</span>
                        <span className="stance-title">{p.title}</span>
                        <span className="stance-count">发言 {countBy.get(p.id) ?? 0} 次</span>
                      </p>
                      <p className="stance-text">{finalView(p)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <aside className="summary-side" aria-label="最终共识与分歧">
            <h2 className="summary-h2">最终共识与分歧</h2>
            <InsightBoard insights={d.insights} participants={d.participants} variant="final" />
          </aside>
        </div>
      </div>
    </article>
  )
}
