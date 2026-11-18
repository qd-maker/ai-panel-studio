// 与 docs/API.md 的响应结构一一对应。时间字段为 UTC ISO 8601 字符串。

export type DiscussionStatus =
  | 'draft'
  | 'lineup_ready'
  | 'running'
  | 'summarizing'
  | 'done'
  | 'failed'
  | 'aborted'

export type Role = 'host' | 'expert'

export type HostAct = 'opening' | 'question' | 'bridge' | 'closing'
export type ExpertAct = 'point' | 'supplement' | 'rebut' | 'answer'
export type UtteranceAct = HostAct | ExpertAct

export type AgentStatus = 'idle' | 'preparing' | 'speaking'
export type InsightKind = 'consensus' | 'divergence'
export type InsightStatus = 'emerging' | 'confirmed' | 'resolved' | 'dropped'
export type SummarySource = 'llm' | 'fallback'

export type ErrorCode =
  | 'DISCUSSION_NOT_FOUND'
  | 'INVALID_STATE_TRANSITION'
  | 'LINEUP_GENERATING'
  | 'VALIDATION_ERROR'
  | 'TOO_MANY_RUNNING'
  | 'LLM_UNAVAILABLE'
  | 'LLM_BAD_OUTPUT'
  | 'INTERNAL_ERROR'
  | 'UNAUTHORIZED'
  | 'TOO_MANY_ATTEMPTS'
  | 'DAILY_LIMIT_REACHED'

export interface ApiError {
  code: ErrorCode
  message: string
  details: Record<string, unknown> | null
}

export interface Participant {
  id: string
  role: Role
  seat_no: number
  name: string
  profession: string
  title: string
  stance: string
  persona: string
  color: string
}

export type ParticipantBrief = Pick<Participant, 'id' | 'role' | 'name' | 'color'>

export interface Utterance {
  id: number
  seq: number
  participant_id: string
  act: UtteranceAct
  content: string
  reply_to_utterance_id: number | null
  addressed_participant_id: string | null
  created_at: string
}

export interface AgentState {
  participant_id: string
  status: AgentStatus
  focus: string | null
  public_thought: string | null
  version: number
  updated_at: string
}

export interface Insight {
  id: string
  kind: InsightKind
  content: string
  supporter_ids: string[]
  opponent_ids: string[]
  status: InsightStatus
  evidence_utterance_ids: number[]
  version: number
  updated_at: string
}

export interface DiscussionSummary {
  id: string
  topic: string
  status: DiscussionStatus
  expert_count: number
  is_seed: boolean
  participants: ParticipantBrief[]
  utterance_count: number
  latest_utterance: string | null
  created_at: string
  started_at: string | null
  ended_at: string | null
}

export interface DiscussionListResponse {
  items: DiscussionSummary[]
}

export interface DiscussionDetail {
  id: string
  topic: string
  status: DiscussionStatus
  status_reason: string | null
  expert_count: number
  max_expert_turns: number
  expert_turns: number
  is_seed: boolean
  summary: string | null
  summary_source: SummarySource | null
  created_at: string
  started_at: string | null
  ended_at: string | null
  participants: Participant[]
  utterances: Utterance[]
  insights: Insight[]
  agent_states: AgentState[]
  last_event_id: number
}

export interface CreateDiscussionRequest {
  topic: string
  expert_count?: number
}

export interface RegenerateLineupRequest {
  expert_count?: number
}

export interface StartResponse {
  id: string
  status: 'running'
  started_at: string
}

export interface AbortResponse {
  id: string
  status: 'aborted'
  ended_at: string
}

// ---------- SSE ----------

export interface StatusEventData {
  discussion_id: string
  from: DiscussionStatus | null
  to: DiscussionStatus
  reason: string | null
  at: string
}

export interface UtteranceEventData {
  discussion_id: string
  utterance: Utterance
}

export interface AgentStateEventData {
  discussion_id: string
  agent_state: AgentState
}

export interface InsightEventData {
  discussion_id: string
  op: 'created' | 'updated'
  insight: Insight
}

export interface SummaryEventData {
  discussion_id: string
  summary: string
  summary_source: SummarySource
  at: string
}

export interface DiscussionErrorEventData {
  discussion_id: string
  code: ErrorCode
  message: string
}

export interface SseEventMap {
  status: StatusEventData
  utterance: UtteranceEventData
  agent_state: AgentStateEventData
  insight: InsightEventData
  summary: SummaryEventData
  discussion_error: DiscussionErrorEventData
}
