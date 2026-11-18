import { ACT_LABEL, HOST_ACTS, STATUS_LABEL, isLive } from '../labels'
import type { DiscussionStatus, HostAct } from '../types'
import './HostBar.css'

interface Props {
  topic: string
  status: DiscussionStatus
  /** 主持人最近一次发言的环节；还没开场时为 null */
  currentAct: HostAct | null
  expertTurns: number
  maxExpertTurns: number
  onAbort?: () => void
}

/** 演播厅顶栏：直播状态、话题、主持人当前环节、专家发言进度 */
export default function HostBar({ topic, status, currentAct, expertTurns, maxExpertTurns, onAbort }: Props) {
  const live = isLive(status)
  const progress = Math.min(1, expertTurns / Math.max(1, maxExpertTurns))

  return (
    <header className="hostbar">
      <span className={`hostbar-live ${live ? 'is-live' : ''}`}>
        {live && <span className="live-dot" />}
        {live ? 'LIVE' : STATUS_LABEL[status]}
      </span>

      <h1 className="hostbar-topic">{topic}</h1>

      <ol className="hostbar-steps" aria-label="主持人当前环节">
        {HOST_ACTS.map((act) => (
          <li key={act} className={act === currentAct ? 'is-current' : ''} aria-current={act === currentAct ? 'step' : undefined}>
            {ACT_LABEL[act]}
          </li>
        ))}
      </ol>

      <div className="hostbar-progress" aria-label={`专家发言 ${expertTurns} / ${maxExpertTurns}`}>
        <span className="hostbar-count">
          {expertTurns}
          <span> / {maxExpertTurns}</span>
        </span>
        <span className="hostbar-track">
          <span className="hostbar-fill" style={{ transform: `scaleX(${progress})` }} />
        </span>
      </div>

      {live && onAbort && (
        <button type="button" className="btn hostbar-abort" onClick={onAbort}>
          结束讨论
        </button>
      )}
    </header>
  )
}
