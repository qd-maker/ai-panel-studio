// DDD 阶段的组件预览台：只用 mock 数据，不连后端。
// 「演播厅」视图按发言顺序模拟一场直播，用来检查动效、跟随滚动和条目高亮。
// 真实页面和数据流在后续阶段接入。

import { useState } from 'react'
import DiscussionCard from './components/DiscussionCard'
import LineupEditor from './components/LineupEditor'
import NewDiscussionInput from './components/NewDiscussionInput'
import SummaryView from './components/SummaryView'
import { isLive } from './labels'
import { eduDetail, mockList, techDetail } from './mock'
import StudioPreview from './studio-preview'
import './App.css'

type View = 'home' | 'lineup' | 'studio' | 'summary'
const VIEWS: { id: View; label: string }[] = [
  { id: 'home', label: '首页卡片' },
  { id: 'lineup', label: '阵容编辑' },
  { id: 'studio', label: '演播厅' },
  { id: 'summary', label: '总结' },
]

// ---------------- 首页 ----------------

function HomePreview() {
  const [busy, setBusy] = useState(false)
  const groups = [
    { key: 'live', title: '正在直播', items: mockList.filter((d) => isLive(d.status)) },
    { key: 'ready', title: '待开始', items: mockList.filter((d) => d.status === 'lineup_ready') },
    { key: 'ended', title: '已结束', items: mockList.filter((d) => ['done', 'failed', 'aborted'].includes(d.status)) },
  ].filter((g) => g.items.length > 0)

  return (
    <div className="home scroll-y">
      <div className="home-inner">
        <NewDiscussionInput
          busy={busy}
          onSubmit={() => {
            setBusy(true)
            window.setTimeout(() => setBusy(false), 2000)
          }}
        />
        {groups.map((g) => (
          <section key={g.key} className={`home-group is-${g.key}`}>
            <h2 className="home-group-title">
              {g.title} <span>{g.items.length}</span>
            </h2>
            <div className="home-grid">
              {g.items.map((d) => (
                <DiscussionCard key={d.id} discussion={d} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

// ---------------- 阵容 ----------------

function LineupPreview() {
  const [count, setCount] = useState(eduDetail.expert_count)
  const [busy, setBusy] = useState<'regenerating' | 'starting' | null>(null)
  const fake = (kind: 'regenerating' | 'starting') => {
    setBusy(kind)
    window.setTimeout(() => setBusy(null), 1600)
  }
  return (
    <div className="single">
      <LineupEditor
        topic={eduDetail.topic}
        participants={eduDetail.participants}
        expertCount={count}
        onExpertCountChange={setCount}
        onRegenerate={() => fake('regenerating')}
        onConfirm={() => fake('starting')}
        busy={busy}
      />
    </div>
  )
}

// ---------------- 总结 ----------------

function SummaryPreview() {
  const [pending, setPending] = useState(false)
  const d = pending ? { ...techDetail, status: 'summarizing' as const, summary: null } : techDetail
  return (
    <div className="single">
      <SummaryView discussion={d} pending={pending} />
      <button type="button" className="btn summary-toggle" onClick={() => setPending((v) => !v)}>
        {pending ? '显示总结' : '查看生成中状态'}
      </button>
    </div>
  )
}

// ---------------- 外壳 ----------------

export default function App() {
  const [view, setView] = useState<View>('studio')
  return (
    <div className="app">
      <header className="app-bar">
        <span className="app-brand">
          AI 圆桌演播厅 <em>组件预览 · mock 数据</em>
        </span>
        <nav className="app-nav">
          {VIEWS.map((v) => (
            <button key={v.id} type="button" className={`app-nav-btn ${view === v.id ? 'is-on' : ''}`} onClick={() => setView(v.id)}>
              {v.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="app-main">
        {view === 'home' && <HomePreview />}
        {view === 'lineup' && <LineupPreview />}
        {view === 'studio' && <StudioPreview />}
        {view === 'summary' && <SummaryPreview />}
      </main>
    </div>
  )
}
