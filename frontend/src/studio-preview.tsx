// 演播厅预览：用科技场的 mock 数据按发言顺序模拟一场直播。
// 布局：舞台 + 席位 + 记录。三档宽度见 studio-preview.css。

import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import HostBar from './components/HostBar'
import InsightBoard from './components/InsightBoard'
import SeatBar from './components/SeatBar'
import Stage from './components/Stage'
import TranscriptPanel from './components/TranscriptPanel'
import { techDetail } from './mock'
import type { AgentState, DiscussionStatus, HostAct, Participant } from './types'
import './studio-preview.css'

const START_AT = 3
const PREPARE_MS = 1500
const GAP_MS = 1200
const TYPE_MS = 45 // 与 Stage 的逐字速度一致

// 小窗内容取自 seed 的观点句（后端已校验不含发言意图），预览台不自己拼文案
const seedViews = new Map(techDetail.agent_states.map((s) => [s.participant_id, s]))

function mockState(p: Participant, status: AgentState['status'], version: number): AgentState {
  const view = seedViews.get(p.id)
  return {
    participant_id: p.id,
    status,
    focus: view?.focus ?? null,
    public_thought: view?.public_thought ?? null,
    version,
    updated_at: new Date().toISOString(),
  }
}

function useMediaQuery(q: string) {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(q)
      m.addEventListener('change', cb)
      return () => m.removeEventListener('change', cb)
    },
    () => window.matchMedia(q).matches,
  )
}

function useMockLive() {
  const d = techDetail
  const [shown, setShown] = useState(START_AT)
  const [states, setStates] = useState<Record<string, AgentState>>({})
  const [tick, setTick] = useState(0)
  const experts = d.participants.filter((p) => p.role === 'expert')
  const byId = useMemo(() => new Map(d.participants.map((p) => [p.id, p])), [d])

  useEffect(() => {
    if (shown >= d.utterances.length) return
    const next = d.utterances[shown]
    const speaker = byId.get(next.participant_id)!
    const v = tick * 10
    const timers: number[] = []
    const set = (patch: Record<string, AgentState>) => setStates((s) => ({ ...s, ...patch }))

    if (speaker.role === 'expert') {
      // 准备发言：下一位发言人 + 另一位也想发言的专家
      const other = experts[(experts.indexOf(speaker) + 1) % experts.length]
      set({ [speaker.id]: mockState(speaker, 'preparing', v + 1), [other.id]: mockState(other, 'preparing', v + 1) })
      timers.push(window.setTimeout(() => set({ [other.id]: mockState(other, 'idle', v + 2) }), PREPARE_MS))
    }
    const appendAt = speaker.role === 'expert' ? PREPARE_MS + 300 : GAP_MS
    timers.push(
      window.setTimeout(() => {
        set({ [speaker.id]: mockState(speaker, 'speaking', v + 3) })
        setShown((n) => n + 1)
      }, appendAt),
    )
    const doneAt = appendAt + next.content.length * TYPE_MS + GAP_MS
    timers.push(
      window.setTimeout(() => {
        set({ [speaker.id]: mockState(speaker, 'idle', v + 4) })
        setTick((t) => t + 1)
      }, doneAt),
    )
    return () => timers.forEach((t) => window.clearTimeout(t))
    // tick 推进下一条；shown 变化不重启计时
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick])

  const utterances = d.utterances.slice(0, shown)
  const visibleIds = new Set(utterances.map((u) => u.id))
  const insights = d.insights.filter((i) => i.evidence_utterance_ids.every((id) => visibleIds.has(id)))
  const lastHost = [...utterances].reverse().find((u) => byId.get(u.participant_id)?.role === 'host')
  const finished = shown >= d.utterances.length
  const status: DiscussionStatus = finished ? 'done' : lastHost?.act === 'closing' ? 'summarizing' : 'running'

  const restart = () => {
    setStates({})
    setShown(START_AT)
    setTick((t) => t + 1)
  }

  return {
    d,
    byId,
    utterances,
    insights,
    status,
    states,
    currentAct: (lastHost?.act ?? null) as HostAct | null,
    expertTurns: utterances.filter((u) => byId.get(u.participant_id)?.role === 'expert').length,
    finished,
    restart,
  }
}

type Tab = 'record' | 'insights'

export default function StudioPreview() {
  const live = useMockLive()
  const [tab, setTab] = useState<Tab>('record')
  const wide = useMediaQuery('(min-width: 1600px)')

  const onStage = live.utterances.at(-1) ?? null
  const history = live.utterances.slice(0, -1)
  const replyTo = onStage?.reply_to_utterance_id ? live.d.utterances.find((u) => u.id === onStage.reply_to_utterance_id) : undefined
  const targetName =
    (replyTo && live.byId.get(replyTo.participant_id)?.name) ??
    (onStage?.addressed_participant_id ? live.byId.get(onStage.addressed_participant_id)?.name : null)

  return (
    <div className="studio">
      <HostBar
        topic={live.d.topic}
        status={live.status}
        currentAct={live.currentAct}
        expertTurns={live.expertTurns}
        maxExpertTurns={live.d.max_expert_turns}
        onAbort={() => {}}
      />

      <div className="studio-grid" data-tab={tab}>
        <div className="area-seats">
          <SeatBar participants={live.d.participants} states={live.states} orientation={wide ? 'column' : 'row'} />
        </div>

        <div className="area-stage">
          <Stage
            utterance={onStage}
            participants={live.d.participants}
            targetName={targetName}
            speakerState={onStage ? live.states[onStage.participant_id] : undefined}
          />
        </div>

        <nav className="area-tabs" aria-label="切换记录和共识分歧">
          <button type="button" className={tab === 'record' ? 'is-on' : ''} onClick={() => setTab('record')}>
            现场记录
          </button>
          <button type="button" className={tab === 'insights' ? 'is-on' : ''} onClick={() => setTab('insights')}>
            共识与分歧
          </button>
        </nav>

        <div className="area-record">
          <TranscriptPanel utterances={history} allUtterances={live.utterances} participants={live.d.participants} />
        </div>

        <div className="area-insights">
          <InsightBoard insights={live.insights} participants={live.d.participants} />
        </div>
      </div>

      {live.finished && (
        <button type="button" className="btn btn-primary studio-replay" onClick={live.restart}>
          重新播放
        </button>
      )}
    </div>
  )
}
