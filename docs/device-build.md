# 装到平板（A 真机验收 / D 演示打包）

> 状态（2026-09-18）：**尚未在任何真机上构建或运行。** 本文是操作步骤；配置（`apps/mobile/eas.json`、`app.json` 的包名与局域网设置、`expo-dev-client` 依赖）已入库，但没有实际跑过 EAS 构建。第一次在真机上跑通后，请把结果记到 `docs/status.md`。

## 选哪条路

| 方式 | 适合 | 需要 | 说明 |
|---|---|---|---|
| Expo Go | 最快看到效果、临时验收 | 平板装 Expo Go；电脑和平板登录**同一个** Expo 账号 | SDK 57 起，iOS 上的 Expo Go 要求终端（`npx expo login`）和 App 内都登录同一账号。若 App Store 版 Expo Go 还不支持 SDK 57，用 `eas go` 装对应版本，或改用下面的开发版 |
| 开发版（Development Build） | 现场演示、长期使用 | Expo 账号；iPad 还需要 Apple 开发者账号并登记设备 | 装的是自己的 App（LivingMind 图标），JS 仍从电脑的开发服务器加载 |

## 共同准备

1. 电脑和平板连同一个 Wi-Fi；查电脑局域网 IP（macOS：`ipconfig getifaddr en0`）。
2. 启动后端（只在可信网络这样做）：

   ```bash
   cd backend
   LIVINGMIND_DEMO_LOCAL_HOUR=20 .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. App 指向后端：`apps/mobile/.env` 写 `EXPO_PUBLIC_API_BASE_URL=http://<电脑IP>:8000`（等号两边不要空格），然后 `npx expo start --clear`。
   不写这一行就是前端模拟模式，界面上会标“前端模拟”。

## Expo Go

```bash
cd apps/mobile
npx expo login
npx expo start --clear      # 平板上的 Expo Go 登录同一账号后扫码
```

## 开发版（EAS）

```bash
npm install -g eas-cli
eas login
cd apps/mobile
# Android 平板：生成可直接安装的 APK
eas build --profile development --platform android
# iPad：先登记设备（需要 Apple 开发者账号），再构建
eas device:create
eas build --profile development --platform ios
# 装好后，电脑上启动开发服务器，平板打开 LivingMind 连接
npx expo start --dev-client --clear
```

- 包名 / Bundle ID 暂定 `com.livingmind.demo`（`app.json`），与已有 App 冲突时改掉即可。
- iOS 已开启 `NSAllowsLocalNetworking`，允许用 `http://` 访问局域网后端；首次连接时系统会询问“本地网络”权限，要点允许。
- 开发版是 debug 包，Android 允许局域网 `http://`。以后如果做正式（release）包，需要另配 HTTPS 或 `expo-build-properties` 的明文流量设置，本轮不做。
- `development-simulator` 配置用于在 Mac 上生成 iOS 模拟器包。

## 真机验收清单（对应 A）

| 项 | 通过标准 |
|---|---|
| 横竖屏 | iPad 横竖屏都不溢出；平板宽度时右侧显示“房间现在” |
| 前端模拟模式 | 不配后端地址也能走完：选起床时间 → 休息 → 确认 → 模拟入睡 → 模拟室温 → 快进整晚 → 停止 |
| 后端模式 | 头部显示后端地址；设备数值来自后端虚拟设备 |
| 断网 | 关掉后端后点确认，提示“无法连接后端 / 可能已过期”，不回退到模拟数据 |
| 准备演示 | “我的”页点准备演示后回到林悦、舒适优先、设备 80/26/100 |
| 动效 | 系统开启“减弱动态效果”后，入场与呼吸动画关闭 |
| 键盘 | 输入框不被键盘挡住 |
| 夜间演示 | 选 06:30 / 07:00 / 07:30 之一后，计划的最后一步时间一致；“模拟已入睡”只执行关灯步骤一次 |
| 失败状态 | 任何后端错误不应显示为“已完成”；App 明确显示错误或服务执行失败 |

## 参考

- [Expo SDK 57 changelog](https://expo.dev/changelog/sdk-57)
- [Running an Expo SDK 57 app in Expo Go（登录要求）](https://dev.to/expo/running-an-expo-sdk-57-app-in-expo-go-you-now-need-to-be-logged-in-on-both-ends-32ef)
- [Introduction to development builds](https://docs.expo.dev/develop/development-builds/introduction/)
- [Configure a development build in cloud](https://docs.expo.dev/tutorial/eas/configure-development-build/)
