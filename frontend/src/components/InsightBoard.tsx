import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { INSIGHT_STATUS_LABEL } from '../labels'
import type { Insight, Participant } from '../types'
import './InsightBoard.css'

interface Props {
  insights: Insight[]
  participants: Participant[]
  /** live：演播厅右栏，自带面板和滚动；final：总结页内嵌，只列最终有效的条目 */
  variant?: 'live' | 'final'
}

/**
 * 高亮做法：列表项的 key 带上 version。条目新增或版本变化时重新挂载，CSS 动画播放一次。
 * 首次渲染时已有的条目（中途加入看到的历史）不高亮。
 */
const versionKey = (i: Insight) => `${i.id}@${i.version}`

/** 有效条目在前，已推翻 / 已化解的沉到底部 */
const rank = (i: Insight) => (i.status === 'dropped' || i.status === 'resolved' ? 1 : 0)

function Avatars({ ids, byId, label }: { ids: string[]; byId: Map<string, Participant>; label: string }) {
  const people = ids.map((id) => byId.get(id)).filter((p): p is Participant => Boolean(p))
  return (
    <span className="ins-avatars" aria-label={`${label}：${people.map((p) => p.name).join('、') || '无'}`}>
      {people.map((p) => (
        <span key={p.id} className="avatar avatar-sm" style={{ '--c': p.color } as CSSProperties} title={p.name}>
          {p.name.slice(0, 1)}
        </span>
      ))}
    </span>
  )
}

export default function InsightBoard({ insights, participants, variant = 'live' }: Props) {
  const byId = useMemo(() => new Map(participants.map((p) => [p.id, p])), [participants])
  const [initialKeys] = useState(() => new Set(insights.map(versionKey)))
  const fresh = (i: Insight) => (initialKeys.has(versionKey(i)) ? '' : 'is-fresh')

  // 总结页只看最终结果：已推翻的条目不再列出
  const shown = variant === 'final' ? insights.filter((i) => i.status !== 'dropped') : insights
  const consensus = shown.filter((i) => i.kind === 'consensus').sort((a, b) => rank(a) - rank(b))
  const divergence = shown.filter((i) => i.kind === 'divergence').sort((a, b) => rank(a) - rank(b))

  return (
    <section className={variant === 'live' ? 'panel insights' : 'insights is-final'} aria-label="共识与分歧">
      <div className={variant === 'live' ? 'insights-scroll scroll-y' : 'insights-scroll'}>
        <div className="ins-section">
          <h2 className="ins-title">
            共识 <span className="ins-count">{consensus.filter((i) => !rank(i)).length}</span>
          </h2>
          {consensus.length === 0 ? (
            <p className="ins-empty">嘉宾们还没有形成共识</p>
          ) : (
            <ul className="ins-list">
              {consensus.map((i) => (
                <li key={versionKey(i)} className={`ins-item st-${i.status} ${fresh(i)}`}>
                  <p className="ins-content">{i.content}</p>
                  <div className="ins-meta">
                    <Avatars ids={i.supporter_ids} byId={byId} label="赞同" />
                    <span className="ins-status">{INSIGHT_STATUS_LABEL[i.status]}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="ins-section">
          <h2 className="ins-title">
            分歧 <span className="ins-count">{divergence.filter((i) => !rank(i)).length}</span>
          </h2>
          {divergence.length === 0 ? (
            <p className="ins-empty">暂未出现明显分歧</p>
          ) : (
            <ul className="ins-list">
              {divergence.map((i) => (
                <li key={versionKey(i)} className={`ins-item spectrum st-${i.status} ${fresh(i)}`}>
                  <p className="ins-content">{i.content}</p>
                  {/* 立场光谱：一条横线，赞成者在左端，反对者在右端 */}
                  <div className="spec-track">
                    <Avatars ids={i.supporter_ids} byId={byId} label="赞成" />
                    <span className="spec-line" aria-hidden="true" />
                    <Avatars ids={i.opponent_ids} byId={byId} label="反对" />
                  </div>
                  <div className="spec-labels">
                    <span>赞成</span>
                    <span className="ins-status">{INSIGHT_STATUS_LABEL[i.status]}</span>
                    <span>反对</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
