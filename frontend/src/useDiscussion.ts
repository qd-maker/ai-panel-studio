// 讨论数据：先拉详情快照，再从快照的 last_event_id 接上 SSE。
//
// - 中途加入：快照里已有历史，SSE 只推之后的事件，不重复也不丢。
// - 断线重连：EventSource 自动重连并带上 Last-Event-ID，后端从断点补发；
//   这里再按事件 id 丢掉已处理过的帧，双保险。
// - 收到终态（done / failed / aborted）后主动 close()，否则 EventSource 会一直重连。

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiFailure } from './api'
import { applyEvent, isTerminal } from './liveState'
import type { DiscussionDetail, SseEventMap } from './types'

const EVENT_NAMES: (keyof SseEventMap)[] = ['status', 'utterance', 'agent_state', 'insight', 'summary', 'discussion_error']

export interface DiscussionState {
  detail: DiscussionDetail | null
  loadError: string | null
  /** 讨论因错误终止时后端推送的中文说明 */
  liveError: string | null
  /** SSE 当前是否在线（断线重连期间为 false） */
  connected: boolean
  setDetail: (d: DiscussionDetail) => void
}

export function useDiscussion(id: string): DiscussionState {
  const [detail, setDetailState] = useState<DiscussionDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [liveError, setLiveError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const lastId = useRef(0)

  const setDetail = useCallback((d: DiscussionDetail) => {
    lastId.current = Math.max(lastId.current, d.last_event_id)
    setDetailState(d)
    setStreamKey((k) => k + 1) // 阵容重新生成后，按新快照重新接流
  }, [])

  // 1. 拉快照
  useEffect(() => {
    let cancelled = false
    setDetailState(null)
    setLoadError(null)
    setLiveError(null)
    lastId.current = 0
    api
      .detail(id)
      .then((d) => {
        if (cancelled) return
        lastId.current = d.last_event_id
        setDetailState(d)
        setStreamKey((k) => k + 1)
      })
      .catch((e: unknown) => !cancelled && setLoadError(e instanceof ApiFailure ? e.message : '加载失败'))
    return () => {
      cancelled = true
    }
  }, [id])

  // 2. 从快照的 last_event_id 接上 SSE
  const status = detail?.status
  useEffect(() => {
    if (!status || isTerminal(status) || streamKey === 0) return
    const es = new EventSource(api.streamUrl(id, lastId.current))
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false) // 浏览器会按服务端给的 retry 自动重连

    for (const name of EVENT_NAMES) {
      es.addEventListener(name, (ev: MessageEvent<string>) => {
        const eid = Number(ev.lastEventId)
        if (eid && eid <= lastId.current) return // 已处理过的帧
        const data = JSON.parse(ev.data)
        if (data.discussion_id !== id) {
          console.error('收到不属于本场讨论的事件', data)
          return
        }
        if (eid) lastId.current = eid
        if (name === 'discussion_error') setLiveError(data.message)
        setDetailState((d) => (d ? { ...applyEvent(d, name, data), last_event_id: lastId.current } : d))
        if (name === 'status' && isTerminal(data.to)) {
          es.close()
          setConnected(false)
          // 终态后再拉一次快照，保证总结、最终状态完整
          api.detail(id).then((d) => setDetailState(d)).catch(() => {})
        }
      })
    }
    return () => es.close()
    // 只在讨论、流的代次变化时重建连接；status 从非终态到非终态不重连
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, streamKey, status && isTerminal(status)])

  return { detail, loadError, liveError, connected, setDetail }
}
