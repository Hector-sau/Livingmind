# 家庭晚间模拟 · Validation notes

本轮验证范围为家庭演示、其真实浏览器操作、虚拟网关与语音接口。家庭默认策略使用规则；可选大模型解析以替身验证约束。设备回读来自模拟器。浏览器视口模拟不能替代 Apple 实机、硬件传感器或真实家庭试用。

## 运行行为测试

从项目根目录执行，无需米家账号、硬件或模型密钥。

```sh
(cd backend && python3 -B -m unittest discover -s tests -p test_family_evening.py -v)
node --test scripts/family_voice.test.cjs
```

- 家庭测试覆盖入户、身份不确定、重复信号、共享空间冲突、临时例外、次日日切、陈旧方案、并发确认、设备离线以及未知回读。默认内存配置的一次完整后端回归为 264 项通过、56 项按配置跳过，报告另列 34 个通过的 subtests；家庭用例已包含其中。
- 浏览器语音接口测试使用替身覆盖转写、能力缺失、权限错误、打断和跨成员迟到回调。真实模型的公开录音烟雾测试以及在本地注册声音模板的方法见[说话人实验](family-voice.md)。
- 已在真实 Chromium 中从浏览器控件操作并核对到家、修改、确认、学习、观影、回执未知及次日偏好。手机使用触摸输入模拟完成确认与打开回执，桌面和手机都使用服务端返回的状态。
- 设计取舍来自既有方案及使用场景假设。演示成员均为虚构人物。打扰率、真实家庭满意度和硬件识别率仍需用户研究。

## 核对视口

| 视口 | 布局 | 导出的单屏图像 |
| --- | --- | --- |
| 手机 390 × 844，3× | 一列服务流、底部导航、家庭成员纵向排列 | 1170 × 2532 |
| 手机 375 × 812，3× | 同一路径检查横向溢出、触控和滚动 | 验证，无单独发行图 |
| iPad 竖屏 820 × 1180，2× | 上下排列空间与建议，设备继续向下滚动 | 1640 × 2360 |
| 大屏 iPad 竖屏 1024 × 1366，2× | 触控设备保持上下排列，检查空间图与建议卡的实际位置 | 验证，无单独发行图 |
| iPad 横屏 1180 × 820，2× | 侧栏导航，空间与建议并排 | 2360 × 1640 |

视口单位为 CSS 像素，对应模拟设备的逻辑显示尺寸。原图固定截取单个视口，未使用整页长截图。脚本断言横向页面宽度、DPR 以及核心操作至少约 44 CSS px 的高度，并通过触摸完成确认与回执查看。

## 复现浏览器操作和媒体

QA 脚本使用 Node.js 和锁定版本的 Playwright。在仓库根目录执行下列命令安装测试依赖与 Chromium。

```sh
npm ci --prefix scripts
(cd scripts && npx --no-install playwright install chromium)
```

可用 `PLAYWRIGHT_MODULE` 指定已安装的模块入口，`CHROMIUM_PATH` 指定兼容的本地 Chromium。脚本每次创建独立的回环服务器与家庭状态，退出时关闭。浏览日常演示不需要这些录制依赖。

```sh
node scripts/family-ui-regression.cjs
node scripts/family-film/capture.cjs /tmp/livingmind-qa
node scripts/family-film/viewports.cjs /tmp/livingmind-screens
```

制作无声影片需要支持 H.264 与 GIF 编码的 FFmpeg、Python Pillow，以及可显示中文的字体。在 Linux 上，将 `CAPTION_FONT` 设为已安装的中文 TrueType 或 TTC 字体的完整路径，例如安装 Noto CJK 后可用 `fc-match -f '%{file}' 'Noto Sans CJK SC'` 查询。先用 `--film` 录制真实浏览器操作，再运行 `render`，合成底部中文说明和穿插在录屏中的架构图解、源码片段。

```sh
node scripts/family-film/capture.cjs /tmp/livingmind-film --film
python3 scripts/family-film/finish.py render /tmp/livingmind-film --media docs/media
node scripts/family-film/viewports.cjs docs/media
ffprobe -v error -select_streams v -show_entries stream=codec_name -of csv=p=0 docs/media/family-evening.mp4
ffprobe -v error -select_streams a -show_entries stream=codec_name -of csv=p=0 docs/media/family-evening.mp4
```

两条 `ffprobe` 命令分别检查视频流与音频流。第一条应输出一行 `h264`，第二条应为空。MP4 还含章节数据。打开展示页后，可从「架构章节」分别跳到规划、确认和回执图解，每个跳转取自随影片发布的 WebVTT。逐幕对照 App 的实际读数，可以检查修改后是否只执行所选设备，以及缺失回执是否保留为未知。[分镜文字稿](family-film.md) · [操作场景](../scripts/family-film/story.json)

独立展示页可直接用浏览器打开，也可作为静态站点展示影片与各设备原图。交互模拟 App 由 Python 服务提供。[展示页](index.html)
