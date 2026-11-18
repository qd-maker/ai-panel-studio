// 枚举值 → 中文界面文案。界面上只出现这里列出的词。

import type { AgentStatus, DiscussionStatus, HostAct, InsightStatus, UtteranceAct } from './types'

export const STATUS_LABEL: Record<DiscussionStatus, string> = {
  draft: '草稿',
  lineup_ready: '待开始',
  running: '直播中',
  summarizing: '总结中',
  done: '已结束',
  failed: '异常终止',
  aborted: '已中止',
}

export const ACT_LABEL: Record<UtteranceAct, string> = {
  opening: '开场',
  question: '追问',
  bridge: '串联',
  closing: '收尾',
  point: '观点',
  supplement: '补充',
  rebut: '反驳',
  answer: '回应',
}

export const HOST_ACTS: HostAct[] = ['opening', 'question', 'bridge', 'closing']

export const AGENT_STATUS_LABEL: Record<AgentStatus, string> = {
  idle: '待机',
  preparing: '准备发言',
  speaking: '发言中',
}

export const INSIGHT_STATUS_LABEL: Record<InsightStatus, string> = {
  emerging: '初现',
  confirmed: '确认',
  resolved: '已化解',
  dropped: '已推翻',
}

export const isLive = (s: DiscussionStatus) => s === 'running' || s === 'summarizing'
