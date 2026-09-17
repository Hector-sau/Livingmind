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
| 人物选择、休息计划、确认、设备状态、停止、服务动态 | 多 Agent 协作 |
| Experience Agent 一次模型调用（DeepSeek，规则/模型可切换，失败降级为规则并标注） | 事件触发的持续调整 |
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

选人物 → 输入“我想休息” → 选“规则”或“模型” → 生成计划（设备不变）→ 确认执行（设备改变并回读）→ 查看服务动态 → 停止服务（设备保持当前状态）。右侧“重置演示数据”可回到初始状态。

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

`--host 0.0.0.0` 让同一局域网的平板能访问；只在可信网络这样做。需要改 CORS（仅浏览器预览用）时：`cp .env.example .env` 后加 `--env-file .env`。

打开 http://localhost:8000/health 应返回 `{"status":"ok"}`；接口文档在 http://localhost:8000/docs 。

**启用模型模式（DeepSeek）**：`cp .env.example .env`，填写 `DEEPSEEK_API_KEY`，然后启动时加 `--env-file .env`。密钥只放在后端 `.env`（已被 Git 忽略），绝不写进 App。不填密钥时模型模式会降级为规则计划并标注原因。

验证一次真实模型调用并记录延迟：

```bash
cd backend && set -a && source .env && set +a && .venv/bin/python scripts/try_model.py "我想休息，有点热"
```

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
```

## 安全说明

- 演示后端**没有正式认证**，只在本机或可信局域网运行，不要部署到公网。
- 密钥只放后端环境变量；App 与 Git 中不得出现密钥。本批次不需要任何密钥。
