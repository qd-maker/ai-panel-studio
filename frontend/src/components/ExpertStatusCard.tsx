import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { AGENT_STATUS_LABEL } from '../labels'
import type { AgentState, Participant } from '../types'
import './ExpertStatusCard.css'

interface Props {
  participant: Participant
  state?: AgentState
  /** 进入「准备发言 / 发言中」时，在所在的滚动容器里滚到可见位置 */
  autoReveal?: boolean
}

/** 只滚动最近的可滚动祖先（横向或纵向），不用 scrollIntoView，避免带动整页 */
function revealInScrollParent(el: HTMLElement) {
  let parent = el.parentElement
  while (parent) {
    const cs = getComputedStyle(parent)
    if (/(auto|scroll)/.test(cs.overflowY + cs.overflowX)) break
    parent = parent.parentElement
  }
  if (!parent) return
  const box = parent.getBoundingClientRect()
  const r = el.getBoundingClientRect()
  const dy = r.top < box.top ? r.top - box.top - 8 : r.bottom > box.bottom ? r.bottom - box.bottom + 8 : 0
  const dx = r.left < box.left ? r.left - box.left - 8 : r.right > box.right ? r.right - box.right + 8 : 0
  if (dx || dy) parent.scrollBy({ top: dy, left: dx, behavior: 'smooth' })
}

/** 专家小窗（席位）：头像圈和姓名用专属色，发言中整席被追光点亮 */
export default function ExpertStatusCard({ participant: p, state, autoReveal = false }: Props) {
  const status = state?.status ?? 'idle'
  const ref = useRef<HTMLElement>(null)
  const isHost = p.role === 'host'

  useEffect(() => {
    if (autoReveal && status !== 'idle' && ref.current) revealInScrollParent(ref.current)
  }, [autoReveal, status])

  return (
    <article
      ref={ref}
      className={`seat st-${status} ${isHost ? 'is-host' : ''}`}
      style={{ '--c': p.color } as CSSProperties}
      aria-label={`${p.name}，${AGENT_STATUS_LABEL[status]}`}
    >
      <div className="seat-head">
        <span className="avatar seat-avatar">{p.name.slice(0, 1)}</span>
        <div className="seat-id">
          <h3 className="seat-name guest-name-c">{p.name}</h3>
          <p className="seat-title">{isHost ? '主持人' : p.title}</p>
        </div>
        <span className="seat-status">
          {status === 'speaking' ? (
            <span className="eq" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          ) : (
            <span className="seat-dot" aria-hidden="true" />
          )}
          {AGENT_STATUS_LABEL[status]}
        </span>
      </div>

      {!isHost && (
        <dl className="seat-view" key={state?.version ?? 0}>
          <div>
            <dt>关注</dt>
            <dd className="seat-focus">{state?.focus || '—'}</dd>
          </div>
          <div>
            <dt>思考</dt>
            <dd className="seat-thought">{state?.public_thought || '暂无公开的思考摘要'}</dd>
          </div>
        </dl>
      )}
    </article>
  )
}
