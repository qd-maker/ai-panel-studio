// DDD 阶段的 mock 数据。JSON 由后端 seed 经 Pydantic 响应模型导出，结构与 API 完全一致。

import type { DiscussionDetail, DiscussionListResponse, DiscussionSummary } from '../types'
import detailsJson from './details.json'
import listJson from './discussions.json'

export const mockDetails = detailsJson as unknown as Record<string, DiscussionDetail>
const list = listJson as unknown as DiscussionListResponse

const byTopic = (kw: string) => Object.values(mockDetails).find((d) => d.topic.includes(kw))!

/** 已结束的科技场：演播厅预览用它模拟直播 */
export const techDetail = byTopic('程序员')
/** 待开始的教育场：阵容编辑器预览用 */
export const eduDetail = byTopic('手机')

/** 首页列表。把科技场改成「直播中」，用来展示 LIVE 卡片 */
export const mockList: DiscussionSummary[] = list.items.map((d) =>
  d.id === techDetail.id
    ? { ...d, status: 'running', ended_at: null, utterance_count: 9, latest_utterance: techDetail.utterances[8].content }
    : d,
)
