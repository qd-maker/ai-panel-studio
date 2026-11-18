// 讨论页 /d/:id：按状态显示阵容确认、演播厅或总结。

import { useState } from 'react'
import { api, ApiFailure } from '../api'
import LineupEditor from '../components/LineupEditor'
import SummaryView from '../components/SummaryView'
import { navigate } from '../router'
import type { DiscussionDetail } from '../types'
import { useDiscussion } from '../useDiscussion'
import StudioView from './StudioView'

const errorText = (e: unknown) => (e instanceof ApiFailure ? e.message : '操作失败，请重试')

function LineupStage({ d, onChange }: { d: DiscussionDetail; onChange: (d: DiscussionDetail) => void }) {
  const [count, setCount] = useState(d.expert_count)
  const [busy, setBusy] = useState<'regenerating' | 'starting' | null>(null)
  const [error, setError] = useState<string | null>(d.status === 'draft' ? '阵容生成失败，请重新生成' : null)

  const regenerate = async () => {
    setBusy('regenerating')
    setError(null)
    try {
      onChange(await api.regenerate(d.id, { expert_count: count }))
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  const start = async () => {
    setBusy('starting')
    setError(null)
    try {
      await api.start(d.id) // 状态变化随后从 SSE 推送过来，页面自动切到演播厅
    } catch (e) {
      setError(errorText(e))
      setBusy(null)
    }
  }

  return (
    <LineupEditor
      topic={d.topic}
      participants={d.participants}
      expertCount={count}
      onExpertCountChange={setCount}
      onRegenerate={regenerate}
      onConfirm={d.status === 'lineup_ready' ? start : undefined}
      busy={busy}
      error={error}
    />
  )
}

export default function DiscussionPage({ id }: { id: string }) {
  const { detail: d, loadError, liveError, connected, setDetail } = useDiscussion(id)
  const [showRecord, setShowRecord] = useState(false)

  if (loadError) {
    return (
      <div className="page-message">
        <p>{loadError}</p>
        <button type="button" className="btn" onClick={() => navigate('/')}>
          回到首页
        </button>
      </div>
    )
  }
  if (!d) return <p className="page-message">正在进入演播厅⋯⋯</p>

  if (d.status === 'draft' || d.status === 'lineup_ready') {
    return <LineupStage d={d} onChange={setDetail} />
  }

  if (d.status === 'done' && !showRecord) {
    return (
      <div className="single" data-discussion-id={d.id} data-status={d.status}>
        <SummaryView discussion={d} />
        <button type="button" className="btn page-corner" onClick={() => setShowRecord(true)}>
          回看现场记录
        </button>
      </div>
    )
  }

  const live = d.status === 'running' || d.status === 'summarizing'
  const notice =
    liveError ??
    (d.status === 'failed' || d.status === 'aborted' ? `讨论已结束：${d.status_reason ?? '已中止'}` : null) ??
    (live && !connected ? '连接中断，正在重新连接⋯⋯' : null)

  return (
    <div className="single">
      <StudioView
        discussion={d}
        notice={notice}
        onAbort={live ? () => api.abort(d.id).catch(() => {}) : undefined}
      />
      {d.status === 'done' && (
        <button type="button" className="btn page-corner" onClick={() => setShowRecord(false)}>
          查看总结
        </button>
      )}
    </div>
  )
}
