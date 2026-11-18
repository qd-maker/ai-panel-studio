import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, WheelEvent } from 'react'
import type { Participant, Utterance } from '../types'
import './TranscriptPanel.css'

interface Props {
  /** 历史发言（舞台上正在说的那一句由 Stage 负责，不在这里重复） */
  utterances: Utterance[]
  participants: Participant[]
  /** 所有发言，用来查「回应的是谁」；默认等于 utterances */
  allUtterances?: Utterance[]
}

/** 离底不超过这个距离，视为「在底部」，新内容到达时跟随 */
const FOLLOW_PX = 40
/** 离底超过这个距离，显示「回到最新」按钮 */
const JUMP_PX = 120

const fmtClock = (iso: string) =>
  new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

export default function TranscriptPanel({ utterances, participants, allUtterances }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLOListElement>(null)
  const pinned = useRef(true)
  /** 程序最近一次滚到的位置。滚动位置偏离它，说明是用户在滚 */
  const programmaticTop = useRef<number | null>(null)
  const [unseen, setUnseen] = useState(0)
  const [showJump, setShowJump] = useState(false)

  const byId = useMemo(() => new Map(participants.map((p) => [p.id, p])), [participants])
  const uttById = useMemo(() => new Map((allUtterances ?? utterances).map((u) => [u.id, u])), [allUtterances, utterances])

  const distanceToBottom = () => {
    const el = scrollRef.current
    return el ? el.scrollHeight - el.scrollTop - el.clientHeight : 0
  }

  const scrollToBottom = () => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    programmaticTop.current = el.scrollTop
  }

  const releaseFollow = () => {
    pinned.current = false
    programmaticTop.current = null
    setShowJump(distanceToBottom() > JUMP_PX)
  }

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    if (programmaticTop.current !== null && Math.abs(el.scrollTop - programmaticTop.current) <= 1) return
    programmaticTop.current = null
    const d = distanceToBottom()
    pinned.current = d <= FOLLOW_PX
    setShowJump(d > JUMP_PX)
    if (pinned.current) setUnseen(0)
  }

  // 滚轮向上的那一刻就停止跟随，不等滚动事件
  const onWheel = (e: WheelEvent) => {
    if (e.deltaY < 0) releaseFollow()
  }

  const jumpToLatest = () => {
    pinned.current = true
    setUnseen(0)
    setShowJump(false)
    scrollToBottom()
  }

  useLayoutEffect(() => {
    scrollToBottom()
  }, [])

  // 内容高度变化时：在底部就跟随，否则不动
  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const ro = new ResizeObserver(() => {
      if (!pinned.current) return
      // 先自己比一次：用户已经离开程序设定的位置（滚动事件可能还没派发），就停止跟随
      const el = scrollRef.current
      if (el && programmaticTop.current !== null && el.scrollTop < programmaticTop.current - 1) {
        releaseFollow()
        return
      }
      scrollToBottom()
    })
    ro.observe(list)
    return () => ro.disconnect()
  }, [])

  const prevCount = useRef(utterances.length)
  useEffect(() => {
    const added = utterances.length - prevCount.current
    prevCount.current = utterances.length
    if (added > 0 && !pinned.current) setUnseen((v) => v + added)
  }, [utterances.length])

  return (
    <section className="transcript" aria-label="现场记录">
      <div className="transcript-scroll scroll-y" ref={scrollRef} onScroll={onScroll} onWheel={onWheel}>
        {utterances.length === 0 && <p className="transcript-empty">之前的发言会记录在这里</p>}
        <ol className="transcript-list" ref={listRef}>
          {utterances.map((u) => {
            const p = byId.get(u.participant_id)
            if (!p) return null
            const replyTo = u.reply_to_utterance_id ? uttById.get(u.reply_to_utterance_id) : undefined
            const target = (replyTo && byId.get(replyTo.participant_id)) ?? (u.addressed_participant_id ? byId.get(u.addressed_participant_id) : undefined)
            return (
              <li key={u.id} className="utt" data-utt-id={u.id} style={{ '--c': p.color } as CSSProperties}>
                <span className="avatar avatar-sm utt-avatar">{p.name.slice(0, 1)}</span>
                <div className="utt-body">
                  <div className="utt-caption">
                    <span className="utt-name guest-name-c">{p.name}</span>
                    <span className="utt-title">{p.role === 'host' ? '主持人' : `${p.profession} · ${p.title}`}</span>
                    {target && <span className="utt-target">→ {target.name}</span>}
                    <time className="utt-time" dateTime={u.created_at}>
                      {fmtClock(u.created_at)}
                    </time>
                  </div>
                  <p className="utt-text">{u.content}</p>
                </div>
              </li>
            )
          })}
        </ol>
      </div>

      {showJump && (
        <button type="button" className="transcript-jump" onClick={jumpToLatest}>
          {unseen > 0 ? `有 ${unseen} 条新发言` : '回到最新'} ↓
        </button>
      )}
    </section>
  )
}
