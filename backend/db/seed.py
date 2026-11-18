"""导入 5 场预设样例讨论。

- 3 场为 lineup_ready：只有阵容，首页点开即可开始。
- 2 场为 done：带完整 transcript、共识与分歧、总结和公开事件，首页打开就有内容可看。

可重复执行：每次先删除旧的样例（is_seed = 1），再重新插入。id 由固定的 key 派生，重复导入后不变。

用法（在 backend 目录下）：
    python -m db.seed
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Connection, Engine, text

from app import schemas
from app.db import get_engine

from app.palette import EXPERT_COLORS, HOST_COLOR  # noqa: E402  与线上生成用同一份色板
BASE_TIME = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)


def seed_id(*parts: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, "ai-panel-studio/seed/" + "/".join(parts)).hex


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 样例数据
# transcript 每项：(发言人, act, 内容, 回应第几条发言, 点名对象)
# insights 每项的 evidence 是发言序号 seq；条目在它引用的最后一条发言之后提炼出来
# ---------------------------------------------------------------------------

SEEDS: list[dict] = [
    {
        "key": "tech",
        "topic": "生成式 AI 会让初级程序员岗位消失吗",
        "status": "done",
        "host": {
            "name": "周衡", "profession": "科技播客主理人", "title": "科技访谈节目《深度对谈》主持人",
            "stance": "保持中立，追问论据",
            "persona": "做了八年科技访谈，习惯把抽象争论拉回具体的人和岗位。",
        },
        "experts": [
            {
                "name": "林晓岚", "profession": "劳动经济学者", "title": "某大学经济学院副教授",
                "stance": "AI 正在实质性压缩初级开发岗位",
                "persona": "长期研究技术变革对就业的影响，发言习惯引用招聘数据，关注普通院校毕业生。",
            },
            {
                "name": "陈拓", "profession": "互联网公司技术总监", "title": "某电商平台技术总监",
                "stance": "初级岗位会减少但不会消失，门槛在变",
                "persona": "带过两百人的研发团队，每年参与校招，说话务实，常拿团队里的真实变化举例。",
            },
            {
                "name": "许安", "profession": "独立开发者", "title": "开源项目维护者",
                "stance": "AI 让新人更强，机会在转移而不是消失",
                "persona": "大学毕业后没进公司，靠独立产品和外包谋生，对大厂视角天然怀疑。",
            },
            {
                "name": "何静", "profession": "高校计算机教师", "title": "某职业技术学院软件专业带头人",
                "stance": "问题出在培养体系，课程必须立刻改",
                "persona": "教了十五年编程，正在推动实训课改革，关心学生毕业后的第一份工作。",
            },
        ],
        "transcript": [
            ("H", "opening", "欢迎来到今天的圆桌，我们讨论生成式 AI 会不会让初级程序员岗位消失。四位嘉宾立场各不相同，先请林老师谈谈您看到的数据。", None, "E1"),
            ("E1", "answer", "我们跟踪的招聘数据显示，初级开发岗位的发布量比两年前明显下降。企业正在用 AI 工具替代原本交给新人的重复编码工作。", 1, None),
            ("E3", "rebut", "招聘发布量下降有经济周期的因素，不能全算在 AI 头上。我身边用 AI 的新手，三个月就能独立交付以前要半年才能上手的功能。", 2, None),
            ("E2", "supplement", "新手上手确实变快了，但我们的招聘标准也跟着变了。现在招初级工程师，我更看重他能不能审查 AI 写出来的代码。", 3, None),
            ("H", "question", "何老师，按陈总的说法，企业要的是会审代码的新人，学校现在教得出来吗？", None, "E4"),
            ("E4", "answer", "坦白说大部分学校还教不出来，课程仍以手写基础代码为主。我们今年开始把代码审查和 AI 协作写进实训课，但进度比行业慢。", 5, None),
            ("E1", "supplement", "这正是我担心的地方：岗位门槛抬高了，培养体系却跟不上，最先被挤出去的是普通院校的毕业生。", 6, None),
            ("E3", "rebut", "门槛抬高的同时，个人做产品的门槛也降低了。不进大厂，新人也可以靠 AI 接外包、做独立产品。", 7, None),
            ("H", "question", "目前大家都认可新人的能力要求在变，分歧在于岗位总量是减少还是转移。陈总，您怎么看许安说的独立开发这条路？", None, "E2"),
            ("E2", "answer", "独立开发只适合少数人，大多数新人还是需要在团队里积累工程经验。我们明年的初级岗位会减少一些，但不会清零。", 9, None),
            ("E1", "rebut", "「减少一些」乘以整个行业，就是一大批毕业生找不到第一份工作。这不是转移，是实打实的缩减。", 10, None),
            ("E4", "supplement", "所以学校不能只等企业给岗位，要让学生在校期间就做出能上线的项目。有作品的学生，在缩减的市场里依然有竞争力。", 11, None),
            ("H", "question", "许安，如果你现在是一名应届生，你会怎么做？", None, "E3"),
            ("E3", "answer", "我会先用 AI 把一个完整项目做上线，再拿它当求职作品。会用 AI 的新人不怕岗位少，怕的是只会背题。", 13, None),
            ("H", "closing", "感谢四位嘉宾的交锋，下面我来回顾今天的共识和分歧。", None, None),
        ],
        "insights": [
            {
                "kind": "consensus", "content": "初级开发岗位招聘量下降主要是 AI 造成的",
                "supporters": ["E1"], "opponents": ["E3"], "status": "dropped",
                "evidence": [2, 3], "version": 2,
            },
            {
                "kind": "consensus", "content": "企业对初级开发者的要求在提高，审查 AI 生成代码成为关键能力",
                "supporters": ["E2", "E3", "E1", "E4"], "opponents": [], "status": "confirmed",
                "evidence": [4, 6, 7], "version": 2,
            },
            {
                "kind": "divergence", "content": "初级程序员岗位总量会显著减少",
                "supporters": ["E1"], "opponents": ["E3"], "status": "confirmed",
                "evidence": [2, 8, 10, 11], "version": 3,
            },
            {
                "kind": "consensus", "content": "学校课程需要尽快加入 AI 协作和项目实战",
                "supporters": ["E4", "E1", "E3"], "opponents": [], "status": "confirmed",
                "evidence": [6, 12, 14], "version": 2,
            },
            {
                "kind": "divergence", "content": "独立开发能成为多数新人的出路",
                "supporters": ["E3"], "opponents": ["E2"], "status": "emerging",
                "evidence": [8, 10], "version": 1,
            },
        ],
        "summary": (
            "本场讨论围绕生成式 AI 是否会让初级程序员岗位消失展开。四位嘉宾一致认为，企业对新人的要求正在改变，"
            "审查和驾驭 AI 生成代码的能力变得更重要。\n\n"
            "主要分歧在岗位总量上：林晓岚认为初级岗位正在实质性缩减，许安认为机会在向独立开发和小团队转移，"
            "陈拓则认为岗位会减少但不会清零。\n\n"
            "何静提出，学校需要尽快在课程里加入代码审查和项目实战，让学生带着能上线的作品进入就业市场。"
        ),
    },
    {
        "key": "health",
        "topic": "互联网医院的在线问诊能替代基层门诊的常见病首诊吗",
        "status": "done",
        "host": {
            "name": "宋知微", "profession": "健康节目主持人", "title": "健康类节目《问诊室》主持人",
            "stance": "保持中立，关注患者视角",
            "persona": "做过医疗记者，擅长把专业争论翻译成患者听得懂的问题。",
        },
        "experts": [
            {
                "name": "梁启明", "profession": "全科医生", "title": "某社区卫生服务中心主任",
                "stance": "首诊必须线下，问诊替代不了查体",
                "persona": "在社区坐诊二十年，见过很多被当成小病拖成大病的案例，说话谨慎。",
            },
            {
                "name": "方可", "profession": "互联网医疗产品负责人", "title": "某在线问诊平台副总裁",
                "stance": "常见病首诊线上化是大势所趋",
                "persona": "做过分诊系统和处方流转，相信规则和数据能控制风险，讲话节奏快。",
            },
            {
                "name": "赵雪", "profession": "医保政策研究员", "title": "某卫生政策研究院研究员",
                "stance": "先解决医保支付和过度开药，再谈放开",
                "persona": "研究医保支付改革，关注制度设计，习惯先问钱谁出、风险谁担。",
            },
            {
                "name": "罗大川", "profession": "慢病患者代表", "title": "高血压病友社群组织者",
                "stance": "患者最需要方便，线上首诊应该放开",
                "persona": "患高血压十年，组织了上千人的病友群，最在意看病要排多久的队。",
            },
        ],
        "transcript": [
            ("H", "opening", "今天我们讨论互联网医院的在线问诊，能不能替代基层门诊做常见病的首诊。梁主任在社区一线，先请您说说判断。", None, "E1"),
            ("E1", "answer", "我的判断是首诊不能离开线下。很多看起来普通的咳嗽和胸闷，需要听诊和查体才能排除严重问题。", 1, None),
            ("E2", "rebut", "大部分常见病首诊并不需要复杂查体，平台可以用分诊规则把高风险患者转到线下。让所有人都跑一趟社区，反而耽误了真正需要的人。", 2, None),
            ("E4", "supplement", "作为患者，我很认同方便这一点。上班族请半天假去排队，很多人干脆就不看病了。", 3, None),
            ("H", "question", "赵研究员，如果线上首诊放开，医保和监管跟得上吗？", None, "E3"),
            ("E3", "answer", "目前大多数地区医保只覆盖线上复诊，首诊没有纳入支付。放开之前，必须先解决线上开药容易过量的问题。", 5, None),
            ("E2", "rebut", "线上处方全程留痕，监管其实比线下更容易做。过度开药的问题，线下同样存在。", 6, None),
            ("E1", "rebut", "留痕解决的是事后追责，解决不了漏诊。分诊规则再细，也替代不了医生按一按患者的肚子。", 7, None),
            ("H", "question", "大家都认同线上适合一部分人，分歧在于首诊的风险由谁兜底。罗先生，作为患者您愿意承担这个风险吗？", None, "E4"),
            ("E4", "answer", "孩子发烧我还是会去线下。但像我这样的老病号，换季感冒先线上问一问，确实省了很多事。", 9, None),
            ("E3", "supplement", "这说明可以分人群放开，比如先对签约了家庭医生的慢病患者开放线上首诊。这样风险有人兜底，医保也好核算。", 10, None),
            ("E1", "supplement", "如果线上首诊由签约的家庭医生来做，我可以接受。医生了解患者的病史，线上判断就有了依据。", 11, None),
            ("H", "question", "方总，平台愿意和社区家庭医生合作，而不是自己接首诊吗？", None, "E2"),
            ("E2", "answer", "愿意，平台更擅长做连接和随访工具。只要支付规则明确，和社区合作比我们自建医生团队成本更低。", 13, None),
            ("H", "closing", "感谢各位嘉宾，下面是本场讨论的总结。", None, None),
        ],
        "insights": [
            {
                "kind": "consensus", "content": "线上问诊能明显减少患者看病的时间成本",
                "supporters": ["E2", "E4", "E3"], "opponents": [], "status": "confirmed",
                "evidence": [3, 4, 10], "version": 2,
            },
            {
                "kind": "divergence", "content": "常见病首诊可以安全地在线上完成",
                "supporters": ["E2", "E4"], "opponents": ["E1"], "status": "confirmed",
                "evidence": [2, 3, 8], "version": 2,
            },
            {
                "kind": "divergence", "content": "处方留痕足以控制线上过度开药",
                "supporters": ["E2"], "opponents": ["E3", "E1"], "status": "emerging",
                "evidence": [6, 7, 8], "version": 1,
            },
            {
                "kind": "consensus", "content": "可以先对签约家庭医生的慢病患者开放线上首诊",
                "supporters": ["E3", "E1", "E2", "E4"], "opponents": [], "status": "confirmed",
                "evidence": [11, 12, 14], "version": 2,
            },
        ],
        "summary": (
            "本场讨论关注互联网医院能否替代基层门诊承担常见病首诊。嘉宾们认同线上问诊能明显减少患者的时间成本，"
            "也认同首诊的风险需要有人兜底。\n\n"
            "分歧集中在安全性上：梁启明认为查体无法在线上完成，方可认为分诊规则和处方留痕可以控制风险。\n\n"
            "讨论后段形成了一个折中方向：先对签约家庭医生的慢病患者开放线上首诊，由熟悉病史的家庭医生接诊，"
            "同时明确医保支付规则。"
        ),
    },
    {
        "key": "edu",
        "topic": "中小学应该全面禁止学生在校使用手机吗",
        "status": "lineup_ready",
        "host": {
            "name": "韩露", "profession": "教育栏目主持人", "title": "教育访谈栏目《开学第一课》主持人",
            "stance": "保持中立，关注学生本人的感受",
            "persona": "当过三年中学语文老师，提问时常把话题拉回到具体的学生身上。",
        },
        "experts": [
            {
                "name": "王建国", "profession": "中学校长", "title": "某市重点中学校长",
                "stance": "支持全面禁止，手机严重分散注意力",
                "persona": "管理一所三千人的中学，亲历过手机引发的沉迷和霸凌事件，态度坚决。",
            },
            {
                "name": "苏敏", "profession": "青少年心理咨询师", "title": "某青少年心理咨询中心主任",
                "stance": "反对一刀切，禁止会激化师生冲突",
                "persona": "每年接待上百名厌学和亲子冲突的青少年，强调规则要让孩子参与制定。",
            },
            {
                "name": "黎言", "profession": "教育技术研究者", "title": "某师范大学教育技术系讲师",
                "stance": "手机是学习工具，应该教会使用而不是禁止",
                "persona": "研究课堂数字化，主张培养学生的数字素养，常引用国外学校的做法。",
            },
            {
                "name": "周芳", "profession": "家长代表", "title": "初二学生家长、家委会成员",
                "stance": "支持禁止，但学校要提供替代的联络方式",
                "persona": "双职工家庭，孩子放学要自己回家，既担心沉迷，也担心联系不上孩子。",
            },
        ],
    },
    {
        "key": "biz",
        "topic": "新茶饮和咖啡品牌靠 9.9 元价格战能做成长期生意吗",
        "status": "lineup_ready",
        "host": {
            "name": "陆川", "profession": "财经节目主持人", "title": "财经节目《商业观察》主持人",
            "stance": "保持中立，追问账算不算得过来",
            "persona": "财经记者出身，喜欢让嘉宾拿单店模型和具体数字说话。",
        },
        "experts": [
            {
                "name": "钱一鸣", "profession": "消费行业投资人", "title": "某消费基金合伙人",
                "stance": "价格战是烧钱换规模，难以持续",
                "persona": "投过多个连锁餐饮品牌，见过补贴退潮后的关店潮，看重单店盈利。",
            },
            {
                "name": "郑悦", "profession": "连锁咖啡品牌运营总监", "title": "某连锁咖啡品牌运营总监",
                "stance": "低价靠供应链效率支撑，可以长期赚钱",
                "persona": "负责上千家门店的运营，熟悉原料采购和门店人效，坚信规模能摊薄成本。",
            },
            {
                "name": "杜衡", "profession": "加盟商", "title": "经营 6 家茶饮加盟门店",
                "stance": "低价的成本最后都压在加盟商身上",
                "persona": "从一家店做到六家，近一年利润明显变薄，说话直接，常算租金和人工账。",
            },
            {
                "name": "冯小雨", "profession": "消费行为研究者", "title": "某商学院营销学副教授",
                "stance": "低价会改变价格锚点，品牌难再涨价",
                "persona": "研究消费者价格感知，关注品牌长期价值，习惯用实验结论解释消费行为。",
            },
        ],
    },
    {
        "key": "society",
        "topic": "年轻人离开一线城市回老家发展，是更好的选择吗",
        "status": "lineup_ready",
        "host": {
            "name": "秦朗", "profession": "播客主播", "title": "社会话题播客《城与人》主播",
            "stance": "保持中立，请嘉宾讲具体的人生选择",
            "persona": "自己在北京和老家之间来回过两次，提问带着亲身体验。",
        },
        "experts": [
            {
                "name": "吴桐", "profession": "城市经济学者", "title": "某城市规划研究院研究员",
                "stance": "一线城市的机会密度无法替代",
                "persona": "研究人口流动和产业集聚，认为年轻时离开大城市的长期代价被低估。",
            },
            {
                "name": "林小满", "profession": "返乡创业者", "title": "县城民宿和农产品电商创业者",
                "stance": "回老家成本低，机会被严重低估",
                "persona": "在上海工作五年后回到县城，靠民宿和电商养活了一个十人团队。",
            },
            {
                "name": "高远", "profession": "人力资源顾问", "title": "某招聘平台资深顾问",
                "stance": "回乡后职业天花板明显，要看行业",
                "persona": "做了十年中高端招聘，见过不少返乡后又回流的候选人，说话偏冷静。",
            },
            {
                "name": "曹芸", "profession": "社会学研究者", "title": "某大学社会学系副教授",
                "stance": "根源在公共服务差距，不是个人选择题",
                "persona": "研究户籍和公共服务均等化，常把个人困境放到制度背景里讨论。",
            },
        ],
    },
]


# 已结束讨论里每位专家的最终小窗内容：(当前关注点, 公开思考摘要)。
# 只写观点本身，不写「想补充 / 想反驳」这类发言意图（schemas.AgentState 会校验）。
FINAL_VIEWS: dict[str, dict[str, tuple[str, str]]] = {
    "tech": {
        "E1": ("初级岗位的招聘数据", "门槛抬高而培养跟不上，普通院校毕业生最先受冲击"),
        "E2": ("团队真实的招聘标准", "初级岗位会减少但不会清零，审查 AI 代码是新门槛"),
        "E3": ("新人的独立开发路径", "AI 降低了做产品的门槛，机会在转移而不是消失"),
        "E4": ("课程改革的进度", "学校要让学生在校期间就做出能上线的项目"),
    },
    "health": {
        "E1": ("首诊的漏诊风险", "由签约家庭医生做线上首诊可以接受，其他情况仍需查体"),
        "E2": ("平台与社区的分工", "平台做连接和随访，和社区合作比自建医生团队成本低"),
        "E3": ("医保支付规则", "分人群放开，先覆盖签约了家庭医生的慢病患者"),
        "E4": ("患者的时间成本", "换季小病先线上问，孩子发烧这类情况还是去线下"),
    },
}


# ---------------------------------------------------------------------------
# 导入逻辑
# ---------------------------------------------------------------------------


def _insert_event(conn: Connection, discussion_id: str, type_: str, payload: dict, at: datetime) -> int:
    return conn.execute(
        text(
            "INSERT INTO event (discussion_id, visibility, type, payload, created_at) "
            "VALUES (:d, 'public', :t, :p, :c)"
        ),
        {"d": discussion_id, "t": type_, "p": json.dumps(payload, ensure_ascii=False), "c": iso(at)},
    ).lastrowid


def _status_event(conn: Connection, did: str, from_: str, to: str, at: datetime) -> None:
    data = schemas.StatusEventData(discussion_id=did, from_=from_, to=to, at=at)
    _insert_event(conn, did, "discussion.status_changed", data.model_dump(mode="json", by_alias=True), at)


def _seed_one(conn: Connection, spec: dict, index: int) -> str:
    key = spec["key"]
    did = seed_id(key)
    created = BASE_TIME + timedelta(hours=index)
    is_done = spec["status"] == "done"
    transcript = spec.get("transcript", [])
    expert_turns = sum(1 for speaker, *_ in transcript if speaker != "H")
    started = created + timedelta(minutes=2) if is_done else None
    ended = started + timedelta(seconds=20 * (len(transcript) + 1)) if is_done else None

    conn.execute(
        text(
            "INSERT INTO discussion (id, topic, expert_count, status, max_expert_turns, expert_turns, "
            "summary, summary_source, is_seed, created_at, updated_at, started_at, ended_at) "
            "VALUES (:id, :topic, :n, :status, :max_turns, :turns, :summary, :source, 1, "
            ":created, :updated, :started, :ended)"
        ),
        {
            "id": did, "topic": spec["topic"], "n": len(spec["experts"]), "status": spec["status"],
            "max_turns": expert_turns if is_done else 12, "turns": expert_turns,
            "summary": spec.get("summary"), "source": "llm" if is_done else None,
            "created": iso(created), "updated": iso(ended or created),
            "started": iso(started) if started else None, "ended": iso(ended) if ended else None,
        },
    )

    # 嘉宾与小窗
    pid: dict[str, str] = {}
    people = [("H", "host", 0, spec["host"], HOST_COLOR)] + [
        (f"E{i}", "expert", i, e, EXPERT_COLORS[i - 1]) for i, e in enumerate(spec["experts"], start=1)
    ]
    for code, role, seat, p, color in people:
        pid[code] = seed_id(key, code)
        participant = schemas.Participant(id=pid[code], role=role, seat_no=seat, color=color, **p)
        conn.execute(
            text(
                "INSERT INTO participant (id, discussion_id, role, seat_no, name, profession, title, "
                "stance, persona, color, created_at) VALUES (:id, :d, :role, :seat_no, :name, "
                ":profession, :title, :stance, :persona, :color, :c)"
            ),
            {**participant.model_dump(), "d": did, "c": iso(created)},
        )
        focus, thought = FINAL_VIEWS.get(key, {}).get(code, (None, None))
        state = schemas.AgentState(
            participant_id=pid[code], status="idle", focus=focus, public_thought=thought,
            version=1, updated_at=ended or created,
        )
        conn.execute(
            text(
                "INSERT INTO agent_state (participant_id, discussion_id, status, focus, public_thought, "
                "version, updated_at) VALUES (:p, :d, :status, :focus, :thought, :version, :u)"
            ),
            {
                "p": state.participant_id, "d": did, "status": state.status, "focus": state.focus,
                "thought": state.public_thought, "version": state.version, "u": iso(ended or created),
            },
        )

    if not is_done:
        return did

    # 发言、共识与分歧、事件（按时间顺序写入，事件 id 与发生顺序一致）
    _status_event(conn, did, "lineup_ready", "running", started)
    utt_id: dict[int, int] = {}
    insights_by_after: dict[int, list[dict]] = {}
    for ins in spec["insights"]:
        insights_by_after.setdefault(max(ins["evidence"]), []).append(ins)

    for seq, (speaker, act, content, reply_seq, addressed) in enumerate(transcript, start=1):
        at = started + timedelta(seconds=20 * seq)
        if act == "closing":
            _status_event(conn, did, "running", "summarizing", at - timedelta(seconds=2))
        row = {
            "seq": seq, "participant_id": pid[speaker], "act": act, "content": content,
            "reply_to_utterance_id": utt_id[reply_seq] if reply_seq else None,
            "addressed_participant_id": pid[addressed] if addressed else None,
        }
        new_id = conn.execute(
            text(
                "INSERT INTO utterance (discussion_id, participant_id, seq, act, content, "
                "reply_to_utterance_id, addressed_participant_id, created_at) VALUES (:d, :participant_id, "
                ":seq, :act, :content, :reply_to_utterance_id, :addressed_participant_id, :c)"
            ),
            {**row, "d": did, "c": iso(at)},
        ).lastrowid
        utt_id[seq] = new_id
        utterance = schemas.Utterance(id=new_id, created_at=at, **row)
        _insert_event(
            conn, did, "utterance.created",
            schemas.UtteranceEventData(discussion_id=did, utterance=utterance).model_dump(mode="json"), at,
        )

        for n, ins in enumerate(insights_by_after.get(seq, [])):
            ins_at = at + timedelta(seconds=5 + n)
            insight = schemas.Insight(
                id=seed_id(key, "insight", ins["content"]),
                kind=ins["kind"], content=ins["content"], status=ins["status"], version=ins["version"],
                supporter_ids=[pid[c] for c in ins["supporters"]],
                opponent_ids=[pid[c] for c in ins["opponents"]],
                evidence_utterance_ids=[utt_id[s] for s in ins["evidence"]],
                updated_at=ins_at,
            )
            conn.execute(
                text(
                    "INSERT INTO insight (id, discussion_id, kind, content, supporter_ids, opponent_ids, "
                    "status, evidence_utterance_ids, version, created_at, updated_at) VALUES (:id, :d, "
                    ":kind, :content, :sup, :opp, :status, :ev, :version, :c, :c)"
                ),
                {
                    "id": insight.id, "d": did, "kind": insight.kind, "content": insight.content,
                    "sup": json.dumps(insight.supporter_ids), "opp": json.dumps(insight.opponent_ids),
                    "status": insight.status, "ev": json.dumps(insight.evidence_utterance_ids),
                    "version": insight.version, "c": iso(ins_at),
                },
            )
            _insert_event(
                conn, did, "insight.upserted",
                schemas.InsightEventData(discussion_id=did, op="created", insight=insight).model_dump(mode="json"),
                ins_at,
            )

    summary = schemas.SummaryEventData(
        discussion_id=did, summary=spec["summary"], summary_source="llm", at=ended - timedelta(seconds=1)
    )
    _insert_event(conn, did, "summary.ready", summary.model_dump(mode="json"), summary.at)
    _status_event(conn, did, "summarizing", "done", ended)
    return did


def seed(engine: Engine) -> list[str]:
    """删除旧样例并重新导入，返回导入的讨论 id。"""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM discussion WHERE is_seed = 1"))
        return [_seed_one(conn, spec, i) for i, spec in enumerate(SEEDS)]


if __name__ == "__main__":
    ids = seed(get_engine())
    print(f"已导入 {len(ids)} 场样例讨论")
