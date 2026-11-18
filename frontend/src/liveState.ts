// 把 SSE 事件应用到讨论快照上。纯函数，便于推理：同一事件应用两次结果不变（按 id / version 去重）。

import type {
  AgentStateEventData,
  DiscussionDetail,
  DiscussionStatus,
  InsightEventData,
  SseEventMap,
  StatusEventData,
  SummaryEventData,
  UtteranceEventData,
} from './types'

export const TERMINAL: DiscussionStatus[] = ['done', 'failed', 'aborted']
export const isTerminal = (s: DiscussionStatus) => TERMINAL.includes(s)

export function applyEvent<K extends keyof SseEventMap>(d: DiscussionDetail, name: K, data: SseEventMap[K]): DiscussionDetail {
  switch (name) {
    case 'status': {
      const e = data as StatusEventData
      return {
        ...d,
        status: e.to,
        status_reason: e.reason,
        started_at: e.to === 'running' ? e.at : d.started_at,
        ended_at: isTerminal(e.to) ? e.at : d.ended_at,
      }
    }
    case 'utterance': {
      const u = (data as UtteranceEventData).utterance
      if (d.utterances.some((x) => x.id === u.id)) return d
      return { ...d, utterances: [...d.utterances, u].sort((a, b) => a.seq - b.seq) }
    }
    case 'agent_state': {
      const s = (data as AgentStateEventData).agent_state
      const cur = d.agent_states.find((x) => x.participant_id === s.participant_id)
      if (cur && cur.version >= s.version) return d
      return { ...d, agent_states: [...d.agent_states.filter((x) => x.participant_id !== s.participant_id), s] }
    }
    case 'insight': {
      const i = (data as InsightEventData).insight
      const cur = d.insights.find((x) => x.id === i.id)
      if (cur && cur.version >= i.version) return d
      return cur ? { ...d, insights: d.insights.map((x) => (x.id === i.id ? i : x)) } : { ...d, insights: [...d.insights, i] }
    }
    case 'summary': {
      const e = data as SummaryEventData
      return { ...d, summary: e.summary, summary_source: e.summary_source }
    }
    default:
      return d
  }
}
