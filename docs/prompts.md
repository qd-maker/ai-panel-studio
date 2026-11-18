# 核心 Prompt 记录

开发工具为 Claude Code（Claude 系列模型），应用运行时调用 DeepSeek。每段记录提示词原文和事后复盘。

## Prompt 0 【需求理解】复述作业，确认禁止项
**原文：**

```
我要做一个面试作业：「AI Panel Studio」——AI 圆桌讨论 Web 应用 MVP。作业原文我放在 docs/assignment.md（我会先贴进去）。

这个项目要按「SDD → DDD → TDD → E2E」四个阶段推进，每个阶段我单独给你提示词。今天这一步只做一件事：读完作业，用你自己的话复述给我：
1. 核心功能清单（编号列出）
2. 你认为最容易做错的「禁止项」有哪些
3. 你建议的技术选型及理由。约束：后端 FastAPI + SQLite（作业强制 SQLite），前端 React + Vite + TypeScript，实时推送用 SSE，LLM 用 DeepSeek（OpenAI 兼容接口），Key 只能在后端从环境变量读取。

不要写任何代码，不要建文件。复述完停下等我确认。
```

**复盘：** 目的是在写任何东西之前，先确认 AI 对需求和禁止项的理解跟我一致。第一次发出时 assignment.md 还不存在，AI 没有凭标题猜着复述，而是停下来要原文；拿到原文后，它指出作业写的是「Claude Code + DeepSeek V4 Pro」，跟我实际的工具不符，我据此定下：开发用 Claude，应用内调 DeepSeek。

## Prompt 1 【SDD 阶段】数据建模与 API 契约
**原文：**

```
【SDD 阶段】现在只写文档，不写业务代码。请在 docs/ 下产出三份 markdown：

1. docs/PRD.md
   - 用户故事 + 每条的验收标准（Given/When/Then）
   - 把作业里所有「禁止」写成可测试的验收标准

2. docs/ER.md（用 mermaid erDiagram）
   至少包含这些实体，字段你来设计，每个字段写类型和含义：
   - discussion（讨论：话题、状态、专家人数、创建时间）
   - participant（主持人/专家：姓名、职业、title、立场、颜色、角色 host/expert）
   - utterance（Transcript 里的公开发言）
   - event（事件流：区分 public 和 internal，internal 如举手/抢话意图不进 Transcript）
   - insight（共识/分歧条目：类型、内容、支持者、状态、更新时间）
   - agent_state（专家小窗：idle / preparing / speaking、当前关注点、公开思考摘要）
   再画一张讨论状态机图（mermaid stateDiagram）：draft → lineup_ready → running → summarizing → done，以及允许的失败/中止分支。

3. docs/API.md
   每个接口写：方法、路径、请求体、响应体、错误码（统一错误格式 {code, message}）。至少包括：
   - POST /api/discussions 创建讨论并生成嘉宾阵容
   - POST /api/discussions/{id}/lineup/regenerate 重新生成阵容
   - POST /api/discussions/{id}/start 确认阵容并开始
   - GET  /api/discussions 列表（首页）
   - GET  /api/discussions/{id} 详情（含已有 transcript、insights、agent_states，用于中途加入观看）
   - GET  /api/discussions/{id}/stream SSE，写清每种事件的 event 名和 data 结构，支持 Last-Event-ID 断线补发
   SSE 只推 public 事件和 agent_state 更新，internal 事件绝不下发。

写完停下，列出你做的关键设计取舍（3–5 条），等我审。
```

**复盘：** 目的是先把实体、事件类型和接口契约定死，让后面的前端、测试和实现都对着同一份文档写。审稿时我追问「错误码有没有考虑 404、409、422、502」，AI 逐个接口对照后找出三处缺口：SSE 的 `after` 参数没有校验；阵容生成期间的并发请求没有定义（补了 409 `LINEUP_GENERATING`，后端给每场讨论加锁）；超时和其他上游失败没有区分（决定都归入 502，原因写进内部日志）。
