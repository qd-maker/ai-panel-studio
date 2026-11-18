// 首页：发起讨论 + 按状态分组的讨论列表（每 5 秒刷新一次）。

import { useEffect, useState } from 'react'
import { api, ApiFailure } from '../api'
import DiscussionCard from '../components/DiscussionCard'
import NewDiscussionInput from '../components/NewDiscussionInput'
import { isLive } from '../labels'
import { navigate } from '../router'
import type { CreateDiscussionRequest, DiscussionSummary } from '../types'

const REFRESH_MS = 5000

export default function HomePage() {
  const [items, setItems] = useState<DiscussionSummary[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      api
        .list()
        .then((r) => alive && setItems(r.items))
        .catch(() => alive && setItems((cur) => cur ?? []))
    load()
    const t = window.setInterval(load, REFRESH_MS)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [])

  const create = async (req: CreateDiscussionRequest) => {
    setBusy(true)
    setError(null)
    try {
      const d = await api.create(req)
      navigate(`/d/${d.id}`)
    } catch (e) {
      // 阵容生成失败时讨论已创建（draft），带用户去阵容页重新生成
      const id = e instanceof ApiFailure ? (e.details?.discussion_id as string | undefined) : undefined
      if (id) navigate(`/d/${id}`)
      else setError(e instanceof ApiFailure ? e.message : '发起失败，请重试')
      setBusy(false)
    }
  }

  const list = items ?? []
  const groups = [
    { key: 'live', title: '正在直播', items: list.filter((d) => isLive(d.status)) },
    { key: 'ready', title: '待开始', items: list.filter((d) => d.status === 'lineup_ready') },
    { key: 'ended', title: '已结束', items: list.filter((d) => ['done', 'failed', 'aborted'].includes(d.status)) },
  ].filter((g) => g.items.length > 0)

  return (
    <div className="home scroll-y">
      <div className="home-inner">
        <NewDiscussionInput busy={busy} error={error} onSubmit={create} />
        {items === null && <p className="home-empty">正在加载讨论列表⋯⋯</p>}
        {items !== null && groups.length === 0 && <p className="home-empty">还没有讨论，在上面输入一个话题开始第一场吧。</p>}
        {groups.map((g) => (
          <section key={g.key} className={`home-group is-${g.key}`}>
            <h2 className="home-group-title">
              {g.title} <span>{g.items.length}</span>
            </h2>
            <div className="home-grid">
              {g.items.map((d) => (
                <DiscussionCard key={d.id} discussion={d} onOpen={(id) => navigate(`/d/${id}`)} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
