import type { CSSProperties } from 'react'
import { STATUS_LABEL, isLive } from '../labels'
import type { DiscussionSummary } from '../types'
import './DiscussionCard.css'

interface Props {
  discussion: DiscussionSummary
  onOpen?: (id: string) => void
}

const fmtTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

export default function DiscussionCard({ discussion: d, onOpen }: Props) {
  const live = isLive(d.status)
  const host = d.participants.find((p) => p.role === 'host')
  const experts = d.participants.filter((p) => p.role === 'expert')

  const body =
    live && d.latest_utterance ? (
      // 进行中：最新一句发言是卡片的主角
      <blockquote className="dcard-quote">{d.latest_utterance}</blockquote>
    ) : d.status === 'lineup_ready' ? (
      <p className="dcard-note">主持人 {host?.name ?? ''} 已就位，阵容确认后即可开场</p>
    ) : (
      <p className="dcard-note">{d.latest_utterance ?? '暂无发言'}</p>
    )

  return (
    <button type="button" className={`dcard ${live ? 'is-live' : ''}`} onClick={() => onOpen?.(d.id)}>
      <div className="dcard-top">
        {live ? (
          <span className="dcard-live">
            <span className="live-dot" />
            LIVE
          </span>
        ) : (
          <span className="dcard-status">{STATUS_LABEL[d.status]}</span>
        )}
        {d.is_seed && <span className="dcard-tag">样例</span>}
        <span className="dcard-time">{fmtTime(d.started_at ?? d.created_at)}</span>
      </div>

      <h3 className="dcard-topic">{d.topic}</h3>

      {body}

      <div className="dcard-foot">
        <span className="dcard-guests" aria-label={`嘉宾：${experts.map((p) => p.name).join('、')}`}>
          {experts.map((p) => (
            <span key={p.id} className="avatar avatar-sm" style={{ '--c': p.color } as CSSProperties} title={p.name}>
              {p.name.slice(0, 1)}
            </span>
          ))}
        </span>
        <span className="dcard-count">
          {d.expert_count} 位专家 · {d.utterance_count} 条发言
        </span>
      </div>
    </button>
  )
}
