import type { CSSProperties } from 'react'
import type { AgentState, Participant } from '../types'
import ExpertStatusCard from './ExpertStatusCard'
import './SeatBar.css'

interface Props {
  participants: Participant[]
  states: Record<string, AgentState | undefined>
  /** row：顶部横排席位条；column：宽屏左侧纵排 */
  orientation?: 'row' | 'column'
}

/** 圆桌席位：主持人居中，专家按座位号分坐两边 */
function arrangeSeats(participants: Participant[]) {
  const host = participants.find((p) => p.role === 'host')
  const experts = participants.filter((p) => p.role === 'expert').sort((a, b) => a.seat_no - b.seat_no)
  const half = Math.ceil(experts.length / 2)
  return [...experts.slice(0, half), ...(host ? [host] : []), ...experts.slice(half)]
}

export default function SeatBar({ participants, states, orientation = 'row' }: Props) {
  const seats = arrangeSeats(participants)
  return (
    <section className={`panel seatbar is-${orientation}`} aria-label="圆桌席位">
      <div className="seatbar-track" style={{ '--n': seats.length } as CSSProperties}>
        {seats.map((p) => (
          <ExpertStatusCard key={p.id} participant={p} state={states[p.id]} autoReveal />
        ))}
      </div>
    </section>
  )
}
