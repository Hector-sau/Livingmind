"""Claim-to-evidence table for the LivingMind finals deck (D / demo packaging).

Writes docs/evidence.md (committed) and, with --pdf, output/pdf/LivingMind-主张证据表.pdf
(rendered by the Playwright Chromium that the e2e tests already use).

Rules: every claim says what the prototype really does, where the proof is, and what kind of
source it is. Simulated things (virtual devices, simulated events and clock, model stub,
designed data) are labelled; claims with no proof in this repo say so.
Usage: python scripts/build_evidence.py [--pdf]
"""

from __future__ import annotations

import argparse
import html
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DECK = "汇报演示/LivingMind_presentationV1（10 页）"

# (slide, claim, status, what the prototype does, evidence, source label)
ROWS: list[tuple[str, str, str, str, str, str]] = [
    ("P01", "面向居住空间的主动体验 Agent：持续理解居住者，主动组织空间服务", "部分实现",
     "家庭卧室原型：一句话 → 计划 → 确认 → 室温事件调整 → 整晚服务。“持续理解”目前是读取本人偏好，不从行为中学习",
     "backend/app/services/rest_service.py；录屏 01–03；网页端到端 20/20", "后端规则 · 虚拟设备 · 模拟事件 / 时钟"),
    ("P01 / P03", "Home Living 为核心，Smart Stay 为延展", "部分实现",
     "只实现家庭场景：1 个空间（家 · 主卧），3 位成员 + 访客；酒店场景没有实现",
     "backend/app/demo/seed.py；docs/test-data.md", "设计的模拟数据"),
    ("P02", "79% 重视互操作性；45% 仍主要用独立 App 控制设备", "外部数据",
     "只用于说明需求背景，不是原型证据", "幻灯片标注：Deloitte 2023 Connected Consumer Study", "外部数据"),
    ("P03", "同一条服务闭环：理解 → 规划 → 执行 → 反馈 → 调整", "已实现（家庭）",
     "主 Agent 编排并记录协作过程；执行后回读设备；室温事件触发重新规划",
     "backend/app/agents/orchestrator/agent.py；tests/test_agents.py（33 项）；tests/test_events.py（10 项）", "后端规则（模型可选）"),
    ("P03", "多成员偏好", "已实现",
     "3 位成员偏好不同，同一句话得到不同计划；每人只能看到自己的偏好；访客不读取任何人的偏好",
     "backend/app/memory/service.py；tests/test_people_and_scenes.py（5 项）；端到端 *-pin-evidence、http-guest-scenes",
     "设计的模拟数据；演示 PIN 不是认证"),
    ("P03", "用户信任与控制权", "已实现",
     "先确认后执行；随时可停止；停止后旧计划失效；重复确认不会重复执行",
     "backend/app/services/rest_service.py；tests/test_rest_flow.py（18 项）", "后端规则"),
    ("P04", "一句话形成方案：柔和灯光、关闭窗帘、舒适温控、勿扰设置", "部分实现",
     "灯光、窗帘、空调已实现（家庭场景）；勿扰设置没有实现",
     "backend/app/rules/rest_rule.py；backend/app/agents/space_execution/agent.py；录屏 01", "虚拟设备"),
    ("P04", "状态变化后主动调整：室温变化 → 重新规划 → 调整空调", "已实现",
     "冷却 30 秒、最多 3 次、同一服务同时只有一个调整、不超出本人偏好 ±3°C、停止后忽略",
     "rest_service.py::inject_event；tests/test_events.py（10 项）；端到端 mock-event、http-event；录屏 02",
     "模拟事件（没有真实传感器）"),
    ("P04", "体验确定舒适边界，能源策略在边界内选择运行方式", "已实现（规则）",
     "舒适范围 = 体验目标 ±1°C；高峰电价时建议空调提高 0.5°C；“舒适优先”只建议，“节能模式”才应用",
     "backend/app/energy/rules.py；tests/test_agents.py；端到端 http-energy-memory",
     "规则估算，非实测；不显示节省比例或金额"),
    ("P05", "拟接入 SpaceMind：任务路由、设备能力映射、权限、空间感知、结果回读、协议连接", "未接入",
     "幻灯片已注明尚未接入。原型里的本地对应：设备能力列表、执行器白名单与参数范围、写入后回读、演示上下文校验",
     "backend/app/adapters/virtual/devices.py；backend/app/harness/executor.py", "虚拟设备；接口待官方文档与联调"),
    ("P05", "Zigbee、Matter、Apple Home 等协议与平台", "未实现", "生态关系示意", "—", "示意"),
    ("P05", "真实设备底座 V2 契约（设备身份、幂等动作 ID、服务代次、回执与错误类型）", "接口预留",
     "DeviceGateway 定义 deviceId / spaceId / actionId / serviceEpoch / accepted-completed-rejected-unknown 四态回执 / 错误类型 / 观测值与观测时间；用可执行契约替身验证协议可实现。没有任何真实对端",
     "backend/app/adapters/protocol.py；tests/test_adapter_protocols.py", "接口预留，未接入真实设备或 SpaceMind"),
    ("P05", "智能音箱语音入口", "接口预留",
     "VoiceGateway 定义 audioId、来源、语言、说话人与空间提示、置信度、播报与取消；转写进入与平板同一条 assistant-message 入口。可信身份必须由应用层解析，不能由转写文本自称。没有麦克风、唤醒词或音箱",
     "backend/app/adapters/voice.py；tests/test_adapter_protocols.py", "接口预留，未接入语音"),
    ("P05", "真实传感器事件源", "接口预留",
     "EnvironmentEventAdapter 定义事件 ID、去重键、来源、空间、采集时间、类型与值；与演示用的 POST /api/spaces/{id}/events 是两个入口，后者永远标注 simulated",
     "backend/app/adapters/events.py；tests/test_adapter_protocols.py", "接口预留，未接入传感器"),
    ("P06", "目标架构 1+2：一个主 Agent，两个专业 Agent", "已实现",
     "主 Agent：规则路由与编排；Experience Agent：可调用大模型；Space Execution Agent：规则（设备能力、空间规则、指令解析、整晚安排）。不是三个大模型 Agent",
     "backend/app/agents/；tests/test_agents.py（24 项）；tests/test_experience_agent.py（14 项）；“场景”页说明卡",
     "只有 Experience Agent 调用模型"),
    ("P06", "Experience Agent 生成体验目标", "已实现；真实调用验证 1 次",
     "2026-09-17 在团队 Mac 上运行 scripts/try_model.py 成功（deepseek-flash，2035 ms，单次）。未配置、超时、网络、HTTP、非法 JSON、结构不符、超出偏离上限都会降级为规则并写明原因",
     "backend/app/services/planner.py；tests/test_experience_agent.py（测试替身）；端到端 http-model-paths（本地模型桩）",
     "真实模型仅单次样本；其余为测试替身 / 模型桩"),
    ("P06", "Context / Memory：当前情境 + 已授权偏好 + 历史反馈", "部分实现",
     "当前设备状态、本人偏好（可在“我的”页编辑）、空间规则已实现；历史反馈没有实现",
     "backend/app/memory/service.py；端到端 http-energy-memory", "设计的模拟数据"),
    ("P06", "Harness：权限、执行约束与异常处理", "已实现（演示级）",
     "白名单与参数范围；每个动作前重查服务状态与代次；设备写入在锁外，停止可中途打断；统一错误格式。权限是演示上下文校验，不是登录认证",
     "backend/app/harness/；tests/test_concurrency.py（2 项）；tests/test_rest_flow.py", "后端规则"),
    ("P06", "已支持空间设备虚拟执行与状态获取", "已实现",
     "有状态虚拟设备（灯光、空调、窗帘），写入后回读，版本号递增",
     "backend/app/adapters/virtual/devices.py；录屏 01", "虚拟设备，不代表真实硬件"),
    ("P06", "读取执行结果，基于结果重规划", "部分实现",
     "室温事件后的重新规划已实现；设备动作失败后的自动重规划没有实现（只记录并提示）",
     "tests/test_events.py", "模拟事件"),
    ("补充", "歧义请求先澄清，不直接变成设备动作", "已实现",
     "否定（“我不想休息，只想关灯”）走设备指令；设备冲突（“先开灯再关灯”）与指代不清（“把那个调低一点”）先提问；待澄清状态按账户、人物、空间与 conversationId 四重隔离，10 分钟过期，可取消，补充后按原意图继续",
     "backend/app/agents/orchestrator/agent.py；contracts/models.py::PendingClarification；alembic 0004；tests/test_agents.py（澄清 3 项）",
     "后端规则；模型也可给出澄清问题"),
    ("补充", "重启恢复语义明确且可查询", "已实现",
     "配置 PostgreSQL 后可恢复计划、服务、整晚步骤、活动与待澄清；崩溃遗留的执行中标记被清理；结果未知的 running 步骤一律取消而不是重放。GET /api/system/recovery 返回存储类型、活跃服务数、取消数、清理数与 deviceStateReconciled",
     "backend/app/services/rest_service.py::recovery_status；tests/test_recovery.py（2 项）",
     "虚拟设备状态仍不跨进程恢复，deviceStateReconciled 为 false"),
    ("补充", "一次表达，持续服务：整晚服务", "已实现",
     "一个服务贯穿整晚：模拟入睡后关灯、01:00 空调调高 1°C、所选起床时间前 30 / 15 / 0 分钟三步唤醒；每步只执行一次；停止取消剩余步骤；任一设备动作失败都不会误标完成",
     "rest_service.py::advance_clock；tests/test_night_service.py（15 项，含并发、重置竞态、部分失败）；端到端 http-night、mock-night、http-night-stop-phone；录屏 03",
     "模拟时钟 / 明确的模拟入睡信号"),
    ("P07", "24 小时家庭并网仿真：规则策略与 MATD3 对比；净运行成本 -$0.02；舒适违规 0 / 0", "已实现（离线展示）",
     "已迁入给定的家庭能源研究快照与其结果；**已在本仓库用同一权重、种子 42 重跑评估，8 项 KPI 与图中数字全部一致（最大差 0.005，仅两位小数取整）**。未重新训练。MATD3 框架在该结果中为单智能体，不参与在线设备控制",
     "simulation/home-energy/research/reproduce_day.py → data/reproduced-day-comparison.json；data/provided-day-comparison.json；provenance/manifest.json；GET /api/spaces/{spaceId}/energy/simulation；空间页“24 小时能源仿真”卡",
     "离线仿真：固定预设日、单智能体、美元/华氏度参数；已复现评估，未重训"),
    ("P08", "49.45% 消费者已使用智能家居；65% 酒店提及劳动力成本压力", "外部数据",
     "只用于说明市场背景，不证明付费意愿", "幻灯片标注的来源（2025 年中国消费者数据；AHLA 2026，n=246）", "外部数据"),
    ("P08", "一套能力，两种商业路径；拟收费单位", "待验证", "幻灯片已标“待验证”", "—", "商业假设"),
    ("P10", "下一步：官方接口联调、家庭样板、酒店试点、规模化推广", "计划", "尚未开始", "—", "计划"),
    ("补充", "平板 App", "部分实现",
     "Expo 应用，平板横竖屏布局；所有界面验证来自网页版；尚未在 iPad 或安卓平板上运行；开发版构建配置已入库",
     "apps/mobile/；docs/device-build.md", "网页版验证"),
    ("工程证据", "Docker 可复现后端", "已实现",
     "Python 3.12 多阶段非 root 镜像；Compose 启动 PostgreSQL、Redis、迁移、API 与两个 Worker；宿主机健康检查与休息闭环通过",
     "backend/Dockerfile；compose.yaml；scripts/verify-t1.sh；docs/status.md", "2026-09-18 Mac Docker Desktop 实测"),
    ("工程证据", "PostgreSQL 业务事实与迁移", "已实现",
     "人物偏好、计划、服务、整晚步骤、动作与活动落库；Alembic 0001→0003 可从空库升级，0003→0002→0003 回退再恢复实测通过",
     "backend/alembic/；backend/app/repositories/sql_store.py；tests/test_persistence.py", "隔离 PostgreSQL 16 测试库"),
    ("工程证据", "LangGraph + Redis 协调", "已实现",
     "legacy / LangGraph 可切换；checkpoint 存 PostgreSQL；Redis 提供 token+TTL 空间锁和冷却快速判断，断连时降级到数据库路径",
     "backend/app/graph/；backend/app/cache/；tests/test_graph_orchestrator.py；tests/test_cache_coordination.py", "真实 PostgreSQL 16 + Redis 7 测试"),
    ("工程证据", "Transactional Outbox 与幂等投影", "已实现",
     "业务事实和 Outbox 同事务；Publisher 重试/死信；Consumer 按 event_id 去重。Compose 实测 7/7 事件发布并消费，重启 Worker 后数量不变",
     "backend/app/events/；backend/workers/；tests/test_outbox_events.py；docs/status.md", "PostgreSQL 数据库队列，非 Kafka"),
    ("工程证据", "T6 完整集成回归", "已实现",
     "默认、PostgreSQL、PostgreSQL+Redis+LangGraph 三套后端组合通过；20 个浏览器场景全部连接 Docker API 通过；GitHub Actions 运行 35333253707 的 6 个 Job 全绿",
     ".github/workflows/ci.yml；apps/mobile/e2e/run_e2e.py；docs/status.md", "本地 Docker / Playwright + GitHub 托管运行"),
    ("工程证据", "E 一致性与可恢复性专项复跑", "已实现",
     "内存+legacy 136/19；PostgreSQL+legacy 150/5；PostgreSQL+Redis+LangGraph 154/1；Alembic 0003↔0004 升降级；legacy/LangGraph 5 组等价；前端 32 项 + 类型检查；契约重新生成逐字节一致；网页端到端 20/20",
     "docs/status.md（E 专项一节）；docs/acceptance.md；docs/agent-engineering-review.md", "2026-09-18 本轮实跑"),
]

CLIPS = [
    ("01-user-trigger.mp4", "约 20 秒", "“我想休息” → 计划卡（协作过程、整晚安排）→ 确认 → 设备变化"),
    ("02-event-adjust.mp4", "约 23 秒", "开始服务 → 模拟室温升高 3°C → 自动调整一次 → 冷却中再次触发被忽略 → 场景时间线"),
    ("03-night-stop.mp4", "约 47 秒", "快进到 23:00 → 自动播放到 07:00，服务结束 → 空间页时间线 → 新的一晚执行一步后手动停止"),
]

TESTS = [
    ("后端：内存 + legacy", "136 通过 / 19 跳过", "backend/tests/"),
    ("后端：PostgreSQL + legacy", "150 通过 / 5 跳过", "backend/tests/"),
    ("后端：PostgreSQL + Redis + LangGraph", "154 通过 / 1 跳过", "backend/tests/"),
    ("Alembic 迁移", "0001→0004；0003→0002→0003 与 0004→0003→0004 通过", "backend/alembic/"),
    ("Outbox / Consumer Compose 链路", "7/7 发布并消费；Worker 重启无重复", "backend/workers/"),
    ("前端逻辑测试 + 类型检查", "32 项", "apps/mobile/tests/"),
    ("网页端到端（平板 / 手机，前端模拟 + Docker API）", "20/20 场景", "apps/mobile/e2e/run_e2e.py"),
    ("契约一致性（后端模型 → 前端类型）", "通过", "scripts/gen-api.sh"),
    ("GitHub Actions 三组合 + Docker E2E", "运行 35333253707：6/6 Job 通过", ".github/workflows/ci.yml"),
]

SOURCES = [
    ("后端规则", "后端固定规则生成，没有调用模型"),
    ("真实模型", "DeepSeek 真实调用；目前只有 1 次成功样本（2035 ms）"),
    ("测试替身 / 模型桩", "自动化测试里代替模型的本地程序，不是真实调用"),
    ("虚拟设备", "后端内存里的有状态设备，不代表真实硬件"),
    ("模拟事件 / 模拟时钟", "室温由按钮或接口给出；整晚时间由按钮推进，不是真实时间"),
    ("设计的模拟数据", "人物、偏好、室外温度、电价时段、评测用例都是设计的"),
    ("网页版验证", "界面测试和录屏来自 Expo 网页导出，不等于平板真机"),
    ("离线仿真", "给定的单日家庭能源研究快照及其已提供指标；不是实时测量、在线控制或重新评估"),
    ("接口预留", "只有协议定义和可执行契约替身测试，没有真实对端；不得描述为已接入"),
]

STATUS_ORDER = ["已实现", "部分实现", "接口预留", "未接入", "未实现", "仓库外", "外部数据", "待验证", "计划"]


def bucket(status: str) -> str:
    return next((s for s in STATUS_ORDER if status.startswith(s)), status)


def counts() -> list[tuple[str, int]]:
    out: dict[str, int] = {}
    for r in ROWS:
        out[bucket(r[2])] = out.get(bucket(r[2]), 0) + 1
    return [(s, out[s]) for s in STATUS_ORDER if s in out]


def markdown() -> str:
    lines = [
        "# 汇报主张与证据对照表",
        "",
        f"对照材料：`{DECK}`。更新：{date.today().isoformat()}。由 `scripts/build_evidence.py` 生成，改表请改脚本。",
        "",
        "状态统计：" + "，".join(f"{s} {n}" for s, n in counts()) + "。",
        "",
        "| 页 | 主张 | 状态 | 原型实际情况 | 证据 | 来源标注 |",
        "|---|---|---|---|---|---|",
    ]
    lines += [f"| {' | '.join(r)} |" for r in ROWS]
    lines += ["", "## 录屏（网页版，`apps/mobile/e2e/record_demo.py` 生成）", "", "| 文件 | 时长 | 内容 |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in CLIPS]
    lines += ["", "每一帧顶部都有字幕：网页版录屏 · 后端虚拟设备 · 规则模式。不是平板真机录屏。", ""]
    lines += ["## 自动检查", "", "| 检查 | 结果 | 位置 |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in TESTS]
    lines += ["", "## 来源标注说明", "", "| 标注 | 含义 |", "|---|---|"]
    lines += [f"| {a} | {b} |" for a, b in SOURCES]
    lines += ["", "## 使用建议", "",
              "- 汇报时说“已实现”的，只用状态为“已实现”的行；“部分实现”要同时说清缺的部分。",
              "- P07 可以说“该固定日的结果已在本仓库复现”；仍不能说已接入实时设备、已重新训练，或证明跨日节能效果。",
              "- “接口预留”的行只能说“协议已定义、可被实现、有契约测试”，不能说已接入真实设备、语音或传感器。",
              "- 外部数据只用于背景，不要用来证明 LivingMind 的效果或付费意愿。", ""]
    return "\n".join(lines)


TONE = {"已实现": "ok", "部分实现": "part", "接口预留": "part", "未接入": "no", "未实现": "no", "仓库外": "warn", "外部数据": "ext", "待验证": "ext", "计划": "ext"}


def page_html() -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td class='pg'>{e(p)}</td><td class='claim'>{e(c)}</td><td class='st'><span class='tag {TONE[bucket(s)]}'>{e(s)}</span></td>"
        f"<td>{e(w)}</td><td class='ev'>{e(v)}</td><td class='src'>{e(src)}</td></tr>"
        for p, c, s, w, v, src in ROWS
    )
    stat = "".join(f"<div class='stat'><b>{n}</b><span>{e(s)}</span></div>" for s, n in counts())
    table = lambda head, data: (
        "<table class='small'><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>"
        + "".join("<tr>" + "".join(f"<td>{e(x)}</td>" for x in r) + "</tr>" for r in data) + "</table>"
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
@page {{ size: A4 landscape; margin: 14mm 12mm 14mm 12mm; }}
body {{ font-family: "Noto Sans CJK SC", "PingFang SC", sans-serif; color: #0f172a; font-size: 9.2pt; line-height: 1.45; }}
h1 {{ font-size: 20pt; margin: 0 0 2mm; color: #0369a1; }}
h2 {{ font-size: 12.5pt; margin: 7mm 0 2mm; color: #0369a1; }}
.sub {{ color: #475569; margin-bottom: 4mm; }}
.stats {{ display: flex; gap: 3mm; margin: 3mm 0 5mm; flex-wrap: wrap; }}
.stat {{ background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 3mm; padding: 2mm 4mm; display: flex; align-items: baseline; gap: 2mm; }}
.stat b {{ font-size: 15pt; color: #0284c7; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #0284c7; color: #fff; text-align: left; padding: 2mm; font-weight: 600; }}
td {{ border-bottom: 1px solid #e2e8f0; padding: 1.8mm 2mm; vertical-align: top; }}
tr {{ page-break-inside: avoid; }}
tbody tr:nth-child(even) td {{ background: #f8fbff; }}
.pg {{ width: 11mm; color: #475569; white-space: nowrap; }}
.claim {{ width: 44mm; font-weight: 600; }}
.st {{ width: 22mm; }}
.ev {{ width: 56mm; color: #334155; font-size: 8.2pt; word-break: break-all; }}
.src {{ width: 30mm; color: #475569; font-size: 8.2pt; }}
.tag {{ display: inline-block; border-radius: 2mm; padding: 0.4mm 1.8mm; font-size: 8pt; font-weight: 700; }}
.ok {{ background: #dcfce7; color: #166534; }} .part {{ background: #e0f2fe; color: #075985; }}
.no {{ background: #f1f5f9; color: #475569; }} .warn {{ background: #fef3c7; color: #92400e; }}
.ext {{ background: #f5f3ff; color: #5b21b6; }}
table.small td, table.small th {{ font-size: 8.8pt; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; }}
ul {{ margin: 1mm 0; padding-left: 5mm; }}
.note {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 3mm; padding: 3mm 4mm; margin-top: 4mm; }}
</style></head><body>
<h1>LivingMind 汇报主张与证据对照表</h1>
<div class="sub">对照材料：{e(DECK)} ｜ 原型仓库：livingmind-app ｜ 更新：{date.today().isoformat()} ｜ 每条主张都写明原型实际情况、证据位置和来源类型</div>
<div class="stats">{stat}</div>
<table><thead><tr><th>页</th><th>主张</th><th>状态</th><th>原型实际情况</th><th>证据</th><th>来源标注</th></tr></thead><tbody>{rows}</tbody></table>
<h2>录屏（网页版）</h2>
{table(["文件", "时长", "内容"], CLIPS)}
<div class="sub">每一帧顶部都有字幕：网页版录屏 · 后端虚拟设备 · 规则模式。不是平板真机录屏。</div>
<div class="two"><div><h2>自动检查</h2>{table(["检查", "结果", "位置"], TESTS)}</div>
<div><h2>来源标注说明</h2>{table(["标注", "含义"], SOURCES)}</div></div>
<div class="note"><b>使用建议</b><ul>
<li>汇报时说“已实现”的，只用状态为“已实现”的行；“部分实现”要同时说清缺的部分。</li>
<li>P07 可以说“该固定日的结果已在本仓库复现”；仍不能说已接入实时设备、已重新训练，或证明跨日节能效果。</li>
<li>“接口预留”的行只能说“协议已定义、可被实现、有契约测试”，不能说已接入真实设备、语音或传感器。</li>
<li>外部数据只用于背景，不要用来证明 LivingMind 的效果或付费意愿。</li></ul></div>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    (REPO / "docs" / "evidence.md").write_text(markdown(), encoding="utf-8")
    print("wrote docs/evidence.md")
    if args.pdf:
        from playwright.sync_api import sync_playwright

        out = REPO / "output" / "pdf"
        out.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(page_html(), wait_until="load")
            page.pdf(
                path=str(out / "LivingMind-主张证据表.pdf"),
                format="A4",
                landscape=True,
                print_background=True,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template="<div style='font-size:7pt;color:#94a3b8;width:100%;text-align:center'>"
                "LivingMind 主张证据表 · 第 <span class='pageNumber'></span> / <span class='totalPages'></span> 页</div>",
                margin={"top": "12mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
            )
            browser.close()
        print("wrote", out / "LivingMind-主张证据表.pdf")


if __name__ == "__main__":
    main()
