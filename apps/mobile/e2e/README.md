# 网页版端到端检查

在浏览器里（Expo 网页导出，react-native-web）自动点完整流程，覆盖平板和手机两种尺寸、前端模拟和真实后端两种模式。

**能证明**：页面流程、来源标注、降级提示、断网反馈在浏览器里工作正常。
**不能证明**：iPad / 安卓真机表现；真实 DeepSeek 调用（这里的模型路径连的是本地桩 `fake_deepseek.py`）。

## 运行

```bash
cd apps/mobile
npm install                                   # 一次
pip install -r e2e/requirements.txt           # 一次
python -m playwright install chromium         # 一次
python e2e/run_e2e.py                         # 构建两份网页版 + 启动服务 + 跑全部场景
```

需要先按 README 建好 `backend/.venv`。也可以用 `BACKEND_PYTHON=/path/to/python` 指定后端解释器。
截图输出到 `e2e/.out/screens/`（已被 Git 忽略）。

## 场景

| 名称 | 内容 |
|---|---|
| mock-flow-tablet / phone | 前端模拟：选人物 → 计划（设备不变）→ 确认 → 运行中 → 停止 |
| http-flow-tablet / phone | 同上，连接真实后端 |
| mock-model-fallback | 前端模拟下选模型模式，显示“前端模拟模式没有模型” |
| http-model-paths | 模型计划（桩）、超时降级、偏离上限降级，并确认降级计划用的是本人偏好 |
| http-offline | 关掉后端后点确认，显示“无法连接后端 / 可能已过期”，不假装成功 |

使用端口 8190、8191（静态页面）、8110（后端）、8195（模型桩），不会占用日常开发的 8000 / 8081。
