import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { ACT_LABEL } from '../labels'
import type { AgentState, Participant, Utterance } from '../types'
import './Stage.css'

interface Props {
  /** 舞台上的这一句（最新一条发言）；还没开场时为 null */
  utterance: Utterance | null
  participants: Participant[]
  /** 这句话是对谁说的（回应的发言人，或主持人点名的嘉宾） */
  targetName?: string | null
  /** 发言人当前的小窗状态，用来判断追光是否亮着 */
  speakerState?: AgentState
  /** 首次渲染时已经存在的发言不播放逐字效果（中途加入） */
  animate?: boolean
}

const TYPE_MS = 45

function Caption({ text, animate }: { text: string; animate: boolean }) {
  const [n, setN] = useState(animate ? 0 : text.length)
  useEffect(() => {
    if (n >= text.length) return
    const t = window.setTimeout(() => setN((v) => v + 1), TYPE_MS)
    return () => window.clearTimeout(t)
  }, [n, text.length])
  return (
    <p className="stage-caption" aria-label={text}>
      <span aria-hidden="true">{text.slice(0, n)}</span>
      {n < text.length && <span className="stage-caret" aria-hidden="true" />}
    </p>
  )
}

/** 舞台：当前发言人大头像 + 姓名 + Title，发言以大字号字幕逐字出现 */
export default function Stage({ utterance, participants, targetName, speakerState, animate = true }: Props) {
  const [firstId] = useState(() => utterance?.id ?? null)
  const speaker = utterance ? participants.find((p) => p.id === utterance.participant_id) : undefined

  if (!utterance || !speaker) {
    return (
      <section className="stage is-empty" aria-label="舞台">
        <p className="stage-wait">主持人就位，等待开场</p>
      </section>
    )
  }

  const isHost = speaker.role === 'host'
  const lit = speakerState?.status === 'speaking'

  return (
    <section className={`stage ${lit ? 'is-lit' : ''}`} aria-label="舞台" aria-live="polite">
      <div className="stage-speaker" style={{ '--c': speaker.color } as CSSProperties}>
        <span className="avatar stage-avatar">{speaker.name.slice(0, 1)}</span>
        <div className="stage-id">
          <p className="stage-name guest-name-c">{speaker.name}</p>
          <p className="stage-title">
            {isHost ? `主持人 · ${ACT_LABEL[utterance.act]}` : `${speaker.profession} · ${speaker.title}`}
            {targetName && <span className="stage-target"> → {targetName}</span>}
          </p>
        </div>
      </div>
      {/* key 换句即重新开始逐字 */}
      <Caption key={utterance.id} text={utterance.content} animate={animate && utterance.id !== firstId} />
    </section>
  )
}
