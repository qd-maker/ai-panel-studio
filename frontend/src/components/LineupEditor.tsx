import type { CSSProperties } from 'react'
import type { Participant } from '../types'
import './LineupEditor.css'

const MIN_EXPERTS = 2
const MAX_EXPERTS = 6

interface Props {
  topic: string
  participants: Participant[]
  expertCount: number
  onExpertCountChange?: (n: number) => void
  onRegenerate?: () => void
  onConfirm?: () => void
  /** 正在重新生成阵容 / 正在开始讨论 */
  busy?: 'regenerating' | 'starting' | null
  error?: string | null
}

function GuestCard({ p }: { p: Participant }) {
  const isHost = p.role === 'host'
  return (
    <article className={`guest ${isHost ? 'is-host' : ''}`} style={{ '--c': p.color } as CSSProperties}>
      <span className="avatar guest-avatar">{p.name.slice(0, 1)}</span>
      <div className="guest-body">
        <p className="guest-role">{isHost ? '主持人' : `专家 ${p.seat_no}`}</p>
        <h3 className="guest-name guest-name-c">{p.name}</h3>
        <p className="guest-title">
          {p.profession} · {p.title}
        </p>
        <p className="guest-stance">{p.stance}</p>
        <p className="guest-persona">{p.persona}</p>
      </div>
    </article>
  )
}

function GuestSkeleton({ host = false }: { host?: boolean }) {
  return (
    <div className={`guest is-skeleton ${host ? 'is-host' : ''}`} aria-hidden="true">
      <span className="sk sk-avatar" />
      <div className="guest-body">
        <span className="sk sk-line short" />
        <span className="sk sk-line" />
        <span className="sk sk-line" />
      </div>
    </div>
  )
}

/** 阵容确认页：主持人在上，专家按座位号排开；底部是人数、重新生成和开始 */
export default function LineupEditor({
  topic,
  participants,
  expertCount,
  onExpertCountChange,
  onRegenerate,
  onConfirm,
  busy = null,
  error = null,
}: Props) {
  const host = participants.find((p) => p.role === 'host')
  const experts = participants.filter((p) => p.role === 'expert').sort((a, b) => a.seat_no - b.seat_no)
  const regenerating = busy === 'regenerating'
  const msg =
    error ??
    (regenerating ? '正在重新生成阵容，大约需要 10 秒⋯⋯' : expertCount !== experts.length ? `重新生成后变为 ${expertCount} 位专家` : null)

  return (
    <section className="lineup" aria-label="嘉宾阵容">
      <div className="lineup-scroll scroll-y" aria-busy={regenerating}>
        <div className="lineup-inner">
          <header className="lineup-head">
            <p className="eyebrow">嘉宾阵容</p>
            <h1 className="lineup-topic">{topic}</h1>
            <p className="lineup-lead">确认阵容后，主持人开场，专家们会按各自的立场展开讨论。</p>
          </header>

          {regenerating ? (
            <>
              <GuestSkeleton host />
              <div className="lineup-grid">
                {Array.from({ length: expertCount }, (_, i) => (
                  <GuestSkeleton key={i} />
                ))}
              </div>
            </>
          ) : (
            <>
              {host && <GuestCard p={host} />}
              <div className="lineup-grid">
                {experts.map((p) => (
                  <GuestCard key={p.id} p={p} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <footer className="lineup-bar">
        <div className="lineup-bar-inner">
          <div className="lineup-count" role="group" aria-label="专家人数">
            <span>专家</span>
            <button
              type="button"
              aria-label="减少一位专家"
              disabled={busy !== null || expertCount <= MIN_EXPERTS}
              onClick={() => onExpertCountChange?.(expertCount - 1)}
            >
              −
            </button>
            <b>{expertCount}</b>
            <button
              type="button"
              aria-label="增加一位专家"
              disabled={busy !== null || expertCount >= MAX_EXPERTS}
              onClick={() => onExpertCountChange?.(expertCount + 1)}
            >
              +
            </button>
            <span>位</span>
          </div>
          {msg ? (
            <p className="lineup-msg" role={error ? 'alert' : undefined}>
              {msg}
            </p>
          ) : (
            <span className="lineup-spacer" />
          )}
          <button type="button" className="btn" disabled={busy !== null} onClick={onRegenerate}>
            {regenerating ? '生成中⋯⋯' : '重新生成'}
          </button>
          <button type="button" className="btn btn-primary" disabled={busy !== null || !onConfirm} onClick={onConfirm}>
            {busy === 'starting' ? (
              '正在开场⋯⋯'
            ) : (
              <>
                <span className="lineup-wide-only">确认阵容，</span>开始讨论
              </>
            )}
          </button>
        </div>
      </footer>
    </section>
  )
}
