# LivingMind App

平板优先、手机兼容的 LivingMind 原型：一个 Expo 原生 App + 一个模块化 FastAPI 后端。

当前范围（第一批）：**最小骨架 → 可点击原型 → 无模型后端闭环**，场景只有 Home Living 的“我想休息”。
接手或协作前先读 [AGENT-HANDOFF.md](AGENT-HANDOFF.md)（统一交接文档，在仓库根目录持续维护）。实际完成情况以 [docs/status.md](docs/status.md) 为准；验收标准见 [docs/acceptance.md](docs/acceptance.md)。

## 三条架构边界

1. **页面不直接控制设备**：页面只调用 `apps/mobile/services/` 的接口；从模拟切到真实 API 不改页面。
2. **Agent 不绕过执行器**：规则计划和（以后的）模型计划都经过同一个执行器检查、执行、回读。
3. **模拟逻辑集中存放**：前端模拟在 `apps/mobile/services/mock/`，后端虚拟设备在 `backend/app/adapters/virtual/`，种子数据在 `backend/app/demo/`。

## 当前做什么 / 不做什么

| 当前做 | 暂不做（后续批次） |
|---|---|
| 对话主页、四个入口、人物切换（演示 PIN）、访客模式、证据面板、场景库 | 整晚定时服务 |
| 1+2 Agent 编排：主 Agent（路由与编排）+ Experience Agent + Space Execution Agent，共享人物记忆、能源规则、Harness 预检，每个计划附协作过程 | 真实设备 / SpaceMind |
| Experience Agent 一次模型调用（DeepSeek，规则/模型可切换，失败降级为规则并标注） | 整晚定时服务 |
| 模拟室温事件触发一次自动调整（冷却、次数上限、停止后忽略） | 真实传感器 |
| 固定规则计划 + 有状态虚拟设备 + 统一执行器 | 整晚定时服务、事件触发调整 |
| 内存存储（重启即重置） | 数据库、正式登录、WebSocket、向量库 |
| 演示身份（demo account） | 真实设备 / SpaceMind / 音箱接入 |

## 目录

```text
apps/mobile/          Expo 原生 App（iPad / Android 平板优先）
backend/app/          FastAPI 后端（契约、规则、执行器、虚拟设备、服务状态）
backend/tests/        后端测试
packages/api-client/  由后端契约生成的 TypeScript 类型（不要手改生成文件）
scripts/              跨端脚本（类型生成）
docs/                 架构、验收、状态
.github/              PR 模板与 CI
```

## 演示流程

上台前：“我的”页点 **准备演示**（重置数据，切回林悦、舒适优先、清空对话、关闭证据面板、回到对话页）。完整讲解顺序见 [`docs/demo-script.md`](docs/demo-script.md)。

选人物 → 输入“我想休息” → 选“规则”或“模型” → 生成计划（设备不变）→ 确认执行（设备改变并回读）→ 点“注入模拟事件”（室温升高 3°C，服务自动调整一次空调）→ 查看服务动态 → 停止服务（设备保持当前状态，之后的事件不再触发动作）。“场景”页顶部的“1+2 Agent 如何协作”卡片可展示最近一次计划的真实协作过程。

计划来源在界面上分四种标注：规则计划、模型计划、规则降级（请求了模型但改用规则，附原因）、前端模拟计划。

## 快速启动

环境：Node.js 20+，Python 3.10+。

### 1. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

演示时建议固定为晚上 8 点（高峰电价时段），能源建议每次一致：

```bash
LIVINGMIND_DEMO_LOCAL_HOUR=20 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

也可以写进 `.env`（`LIVINGMIND_DEMO_LOCAL_HOUR=20`，等号两边不要有空格）。让能源建议固定在高峰电价时段。`--host 0.0.0.0` 让同一局域网的平板能访问；只在可信网络这样做。需要改 CORS（仅浏览器预览用）时：`cp .env.example .env` 后加 `--env-file .env`。

打开 http://localhost:8000/health 应返回 `{"status":"ok"}`；接口文档在 http://localhost:8000/docs 。

**启用模型模式（DeepSeek）**：`cp .env.example .env`，填写 `DEEPSEEK_API_KEY`，然后启动时加 `--env-file .env`。密钥只放在后端 `.env`（已被 Git 忽略），绝不写进 App。不填密钥时模型模式会降级为规则计划并标注原因。

验证真实模型（需要 `.env` 里的密钥，只能在你自己的电脑上跑）：

```bash
cd backend && set -a && source .env && set +a
.venv/bin/python scripts/try_model.py "我想休息，有点热"   # 只测 Agent 一次调用
.venv/bin/python scripts/e2e_real_model.py                 # 可选：后端端到端，5 句话，含延迟统计
.venv/bin/python scripts/e2e_real_model.py --eval          # 可选：用设计的评测集给真实模型打分
```

浏览器端到端也可以用真实模型：`cd apps/mobile && python e2e/run_e2e.py --real-model`。

### 2. App

```bash
cd apps/mobile
npm install
cp .env.example .env        # 按需修改
npx expo start
```

- **模拟模式**：`.env` 里不设置 `EXPO_PUBLIC_API_BASE_URL`，App 使用前端模拟接口，界面顶部显示“前端模拟模式”。
- **后端模式**：设置 `EXPO_PUBLIC_API_BASE_URL=http://<Mac 的局域网 IP>:8000`。平板上不能用 `localhost`（那是平板自己）。查 Mac IP：`ipconfig getifaddr en0`。
- 改了 `.env` 后要用 `npx expo start --clear` 重启，否则旧配置会被缓存。
- 在 iPad 上用 Expo Go 扫码预览；在 Mac 上按 `Shift + i` 选 iPad 模拟器（需要 Xcode）；按 `w` 用浏览器粗看布局。

### 3. 重新生成接口类型

后端契约改动后运行（需先完成后端 venv 安装）：

```bash
./scripts/gen-api.sh
```

## 检查命令

```bash
cd backend && pytest                      # 后端测试
cd apps/mobile && npm run typecheck && npm test   # 前端类型检查 + 逻辑测试
./scripts/gen-api.sh && git diff --exit-code packages/api-client   # 契约一致性
python apps/mobile/e2e/run_e2e.py         # 网页端到端（见 apps/mobile/e2e/README.md）
```

## 安全说明

- 演示后端**没有正式认证**，只在本机或可信局域网运行，不要部署到公网。
- 密钥只放后端环境变量；App 与 Git 中不得出现密钥。本批次不需要任何密钥。
