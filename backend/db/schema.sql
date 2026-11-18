-- AI Panel Studio SQLite schema
-- 字段含义见 docs/ER.md。所有语句可重复执行（IF NOT EXISTS）。
-- 连接时需开启：PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;（由 app/db.py 负责）

-- 讨论
CREATE TABLE IF NOT EXISTS discussion (
    id               TEXT    PRIMARY KEY,
    topic            TEXT    NOT NULL CHECK (length(topic) BETWEEN 5 AND 200),
    expert_count     INTEGER NOT NULL CHECK (expert_count BETWEEN 2 AND 6),
    status           TEXT    NOT NULL CHECK (status IN (
                         'draft', 'lineup_ready', 'running', 'summarizing',
                         'done', 'failed', 'aborted')),
    status_reason    TEXT,
    max_expert_turns INTEGER NOT NULL DEFAULT 12 CHECK (max_expert_turns > 0),
    expert_turns     INTEGER NOT NULL DEFAULT 0  CHECK (expert_turns >= 0),
    summary          TEXT,
    summary_source   TEXT    CHECK (summary_source IN ('llm', 'fallback')),
    is_seed          INTEGER NOT NULL DEFAULT 0  CHECK (is_seed IN (0, 1)),
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL,
    started_at       TEXT,
    ended_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_discussion_status_created
    ON discussion (status, created_at);

-- 主持人与专家
CREATE TABLE IF NOT EXISTS participant (
    id            TEXT    PRIMARY KEY,
    discussion_id TEXT    NOT NULL REFERENCES discussion (id) ON DELETE CASCADE,
    role          TEXT    NOT NULL CHECK (role IN ('host', 'expert')),
    seat_no       INTEGER NOT NULL CHECK (seat_no >= 0),
    name          TEXT    NOT NULL CHECK (length(name) > 0),
    profession    TEXT    NOT NULL CHECK (length(profession) > 0),
    title         TEXT    NOT NULL CHECK (length(title) > 0),
    stance        TEXT    NOT NULL CHECK (length(stance) BETWEEN 1 AND 40),
    persona       TEXT    NOT NULL CHECK (length(persona) BETWEEN 1 AND 120),
    color         TEXT    NOT NULL CHECK (
                      length(color) = 7
                      AND color GLOB '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]'),
    created_at    TEXT    NOT NULL,
    UNIQUE (discussion_id, seat_no),
    UNIQUE (discussion_id, color)
);
-- 每场讨论恰好一位主持人（至多一位由索引保证，至少一位由业务层保证）
CREATE UNIQUE INDEX IF NOT EXISTS uq_participant_one_host
    ON participant (discussion_id) WHERE role = 'host';

-- Transcript 中的公开发言
CREATE TABLE IF NOT EXISTS utterance (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id            TEXT    NOT NULL REFERENCES discussion (id) ON DELETE CASCADE,
    participant_id           TEXT    NOT NULL REFERENCES participant (id) ON DELETE CASCADE,
    seq                      INTEGER NOT NULL CHECK (seq >= 1),
    act                      TEXT    NOT NULL CHECK (act IN (
                                 'opening', 'question', 'bridge', 'closing',
                                 'point', 'supplement', 'rebut', 'answer')),
    content                  TEXT    NOT NULL CHECK (length(content) BETWEEN 1 AND 120),
    reply_to_utterance_id    INTEGER REFERENCES utterance (id) ON DELETE SET NULL,
    addressed_participant_id TEXT    REFERENCES participant (id) ON DELETE SET NULL,
    created_at               TEXT    NOT NULL,
    UNIQUE (discussion_id, seq)
);

-- 事件流（只追加）。AUTOINCREMENT 保证 id 永不复用，可安全作为 SSE 的 id。
CREATE TABLE IF NOT EXISTS event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id TEXT    NOT NULL REFERENCES discussion (id) ON DELETE CASCADE,
    visibility    TEXT    NOT NULL CHECK (visibility IN ('public', 'internal')),
    type          TEXT    NOT NULL,
    payload       TEXT    NOT NULL CHECK (json_valid(payload)),
    created_at    TEXT    NOT NULL
);
-- SSE 补发：WHERE discussion_id = ? AND id > ? ORDER BY id
CREATE INDEX IF NOT EXISTS idx_event_discussion_id
    ON event (discussion_id, id);

-- 共识与分歧条目
CREATE TABLE IF NOT EXISTS insight (
    id                     TEXT    PRIMARY KEY,
    discussion_id          TEXT    NOT NULL REFERENCES discussion (id) ON DELETE CASCADE,
    kind                   TEXT    NOT NULL CHECK (kind IN ('consensus', 'divergence')),
    content                TEXT    NOT NULL CHECK (length(content) BETWEEN 1 AND 80),
    supporter_ids          TEXT    NOT NULL DEFAULT '[]'
                                   CHECK (json_valid(supporter_ids) AND json_type(supporter_ids) = 'array'),
    opponent_ids           TEXT    NOT NULL DEFAULT '[]'
                                   CHECK (json_valid(opponent_ids) AND json_type(opponent_ids) = 'array'),
    status                 TEXT    NOT NULL CHECK (status IN ('emerging', 'confirmed', 'resolved', 'dropped')),
    evidence_utterance_ids TEXT    NOT NULL
                                   CHECK (json_valid(evidence_utterance_ids)
                                          AND json_type(evidence_utterance_ids) = 'array'
                                          AND json_array_length(evidence_utterance_ids) >= 1),
    version                INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at             TEXT    NOT NULL,
    updated_at             TEXT    NOT NULL,
    CHECK (status <> 'resolved' OR kind = 'divergence')
);
CREATE INDEX IF NOT EXISTS idx_insight_discussion_created
    ON insight (discussion_id, created_at);

-- 嘉宾小窗（每位嘉宾一行，存当前状态）
CREATE TABLE IF NOT EXISTS agent_state (
    participant_id TEXT    PRIMARY KEY REFERENCES participant (id) ON DELETE CASCADE,
    discussion_id  TEXT    NOT NULL REFERENCES discussion (id) ON DELETE CASCADE,
    status         TEXT    NOT NULL DEFAULT 'idle' CHECK (status IN ('idle', 'preparing', 'speaking')),
    focus          TEXT    CHECK (focus IS NULL OR length(focus) <= 20),
    public_thought TEXT    CHECK (public_thought IS NULL OR length(public_thought) <= 60),
    version        INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    updated_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_state_discussion
    ON agent_state (discussion_id);
