// 演播厅：舞台 + 席位 + 记录。数据全部来自 useDiscussion 维护的讨论快照。

import { useMemo, useState, useSyncExternalStore } from 'react'
import HostBar from '../components/HostBar'
import InsightBoard from '../components/InsightBoard'
import SeatBar from '../components/SeatBar'
import Stage from '../components/Stage'
import TranscriptPanel from '../components/TranscriptPanel'
import type { AgentState, DiscussionDetail, HostAct } from '../types'
import './StudioView.css'

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

interface Props {
  discussion: DiscussionDetail
  onAbort?: () => void
  /** 页面顶部的提示条，例如断线重连、讨论异常终止 */
  notice?: string | null
}

type Tab = 'record' | 'insights'

export default function StudioView({ discussion: d, onAbort, notice }: Props) {
  const [tab, setTab] = useState<Tab>('record')
  const wide = useMediaQuery('(min-width: 1600px)')

  const byId = useMemo(() => new Map(d.participants.map((p) => [p.id, p])), [d.participants])
  const states = useMemo(() => Object.fromEntries(d.agent_states.map((s) => [s.participant_id, s])) as Record<string, AgentState>, [d.agent_states])

  const onStage = d.utterances.at(-1) ?? null
  const history = d.utterances.slice(0, -1)
  const lastHost = [...d.utterances].reverse().find((u) => byId.get(u.participant_id)?.role === 'host')
  const expertTurns = d.utterances.filter((u) => byId.get(u.participant_id)?.role === 'expert').length
  const replyTo = onStage?.reply_to_utterance_id ? d.utterances.find((u) => u.id === onStage.reply_to_utterance_id) : undefined
  const targetName =
    (replyTo && byId.get(replyTo.participant_id)?.name) ??
    (onStage?.addressed_participant_id ? byId.get(onStage.addressed_participant_id)?.name : null)

  return (
    <div className="studio" data-discussion-id={d.id} data-status={d.status}>
      <HostBar
        topic={d.topic}
        status={d.status}
        currentAct={(lastHost?.act ?? null) as HostAct | null}
        expertTurns={expertTurns}
        maxExpertTurns={d.max_expert_turns}
        onAbort={onAbort}
      />

      {notice && (
        <p className="studio-notice" role="status">
          {notice}
        </p>
      )}

      <div className="studio-grid" data-tab={tab}>
        <div className="area-seats">
          <SeatBar participants={d.participants} states={states} orientation={wide ? 'column' : 'row'} />
        </div>

        <div className="area-stage">
          <Stage
            utterance={onStage}
            participants={d.participants}
            targetName={targetName}
            speakerState={onStage ? states[onStage.participant_id] : undefined}
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
          <TranscriptPanel utterances={history} allUtterances={d.utterances} participants={d.participants} />
        </div>

        <div className="area-insights">
          <InsightBoard insights={d.insights} participants={d.participants} />
        </div>
      </div>
    </div>
  )
}
