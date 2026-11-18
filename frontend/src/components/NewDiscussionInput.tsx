import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import type { CreateDiscussionRequest } from '../types'
import './NewDiscussionInput.css'

const MIN_TOPIC = 5
const MAX_TOPIC = 200
const MIN_EXPERTS = 2
const MAX_EXPERTS = 6

interface Props {
  onSubmit?: (req: CreateDiscussionRequest) => void
  /** 正在生成阵容 */
  busy?: boolean
  error?: string | null
}

/** 首页顶部：输入话题和专家人数，发起一场圆桌 */
export default function NewDiscussionInput({ onSubmit, busy = false, error = null }: Props) {
  const [topic, setTopic] = useState('')
  const [count, setCount] = useState(4)
  const len = topic.trim().length
  const valid = len >= MIN_TOPIC && len <= MAX_TOPIC

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (!valid || busy) return
    onSubmit?.({ topic: topic.trim(), expert_count: count })
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    // 输入法守卫：中文选词时按的回车不提交（Safari 选词时 isComposing 已为 false，要再判 keyCode 229）
    if (e.nativeEvent.isComposing || e.keyCode === 229) return
    if (e.key === 'Enter') submit()
  }

  const hint =
    error ?? (len === 0 ? '话题 5～200 字' : len < MIN_TOPIC ? `再写 ${MIN_TOPIC - len} 个字` : len > MAX_TOPIC ? `超出 ${len - MAX_TOPIC} 字` : null)

  return (
    <form className="composer" onSubmit={submit} aria-busy={busy}>
      <label className="composer-label" htmlFor="new-topic">
        发起一场圆桌
      </label>
      <div className="composer-box">
        <input
          id="new-topic"
          className="composer-input"
          value={topic}
          maxLength={MAX_TOPIC + 20}
          placeholder="例如：远程办公会降低团队创造力吗"
          autoComplete="off"
          disabled={busy}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="composer-row">
          <div className="composer-count" role="group" aria-label="专家人数">
            <span>专家</span>
            <button type="button" aria-label="减少一位专家" disabled={busy || count <= MIN_EXPERTS} onClick={() => setCount(count - 1)}>
              −
            </button>
            <b>{count}</b>
            <button type="button" aria-label="增加一位专家" disabled={busy || count >= MAX_EXPERTS} onClick={() => setCount(count + 1)}>
              +
            </button>
            <span>位</span>
          </div>
          <span className={`composer-hint ${error ? 'is-error' : ''}`} role={error ? 'alert' : undefined}>
            {busy ? '正在生成嘉宾阵容，大约需要 10 秒⋯⋯' : hint}
          </span>
          <span className="composer-len">
            {len}/{MAX_TOPIC}
          </span>
          <button type="submit" className="btn btn-primary composer-submit" disabled={!valid || busy}>
            {busy ? '生成中⋯⋯' : '生成嘉宾阵容'}
          </button>
        </div>
      </div>
    </form>
  )
}
