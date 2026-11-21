# 家庭语音输入与说话人实验

## 在家庭 App 里说一句话

打开「语音」，选当前家庭成员，点麦克风并说「我到家了」或「我想看电视」。识别结果先填入输入框，可以修正，再提交给家庭场景。开始录音会打断正在朗读的回复。关闭面板或切换人物会取消旧录音，迟到的结果会被丢弃。

网页会请求浏览器提供的中文语音转写与朗读服务。浏览器实现可能使用其供应商的联网语音服务。没有麦克风、未授权或浏览器缺少该能力时，仍可打字。「示例」会直接填入明确标记的模拟文字。当前 App 里的人物来自手动选择。说出某个成员的名字不会切换身份。

[浏览器语音识别文档](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)

## 离线比较是谁在说话

声纹实验支持注册声音模板、核对指定成员和在多个模板中选出候选人。它使用 SpeechBrain 的 ECAPA-TDNN 对真实音频计算声纹向量，在本机比对。完成注册后，可以在家庭 App 的语音面板查看候选成员，也可以单独运行命令行。身份选择与方案确认均由用户完成。

以下操作从仓库根目录执行。首次安装和获取官方权重需要联网。使用自己的临时或私有目录保存声音模板，模板包含声纹特征。验证结束后可自行清理该目录。

```bash
python3 -m venv /tmp/livingmind-voice-env
source /tmp/livingmind-voice-env/bin/activate
python -m pip install 'torch==2.8.0' 'torchaudio==2.8.0' 'speechbrain==1.0.3' 'soundfile==0.13.1' 'huggingface-hub==0.25.2'
export FAMILY_VOICE_MODEL=/tmp/livingmind-ecapa
huggingface-cli download speechbrain/spkrec-ecapa-voxceleb \
  --revision 0f99f2d0ebe89ac095bcc5903c4dd8f72b367286 \
  --include '*.ckpt' 'hyperparams.yaml' 'label_encoder.txt' 'example1.wav' 'example2.flac' \
  --local-dir "$FAMILY_VOICE_MODEL"
```

模型到位后可断网运行。下面用模型发行包自带的两段公开语音演示。为真实家庭采样时，请使用成员同意提供的录音。每段 1–30 秒，可以包含不同句子。注册时可传入同一成员的多段语音。系统会统一转为 16 kHz 单声道并对多段单位向量取平均。模板以文件名作为候选标识，重名文件会保留原有注册数据。

```bash
VOICE_TRIAL=$(mktemp -d)
python scripts/family_speaker.py --model "$FAMILY_VOICE_MODEL" enroll \
  "$VOICE_TRIAL/voice-a.json" "$FAMILY_VOICE_MODEL/example1.wav"
python scripts/family_speaker.py --model "$FAMILY_VOICE_MODEL" verify \
  "$VOICE_TRIAL/voice-a.json" "$FAMILY_VOICE_MODEL/example2.flac"
python scripts/family_speaker.py --model "$FAMILY_VOICE_MODEL" enroll \
  "$VOICE_TRIAL/voice-b.json" "$FAMILY_VOICE_MODEL/example2.flac"
python scripts/family_speaker.py --model "$FAMILY_VOICE_MODEL" identify \
  "$FAMILY_VOICE_MODEL/example2.flac" "$VOICE_TRIAL/voice-a.json" "$VOICE_TRIAL/voice-b.json"
```

### 如何读结果

单人比对使用余弦相似度，高于阈值才返回 `match`。多人识别还要求第一名领先第二名达到设定差距，否则返回 `unknown`。默认 `--threshold 0.25` 沿用模型接口的参考值。多人差距 `--margin 0.10` 是演示配置。录音重放也可能获得高分，结果仅作为候选；切换 App 人物、设备授权继续由原有产品流程处理。

2026-11-21 在本地 CPU 实测。以官方 `example1.wav` 注册，同一文件回放为 **1.000000**；与 `example2.flac` 比较为 **0.179902**。两个文件分别注册后，后者回放命中第二个模板。将所需差距临时设为 1.0 可演示 `unknown`。以上用例验证音频读取、声纹计算、判定和拒识分支；家庭实际误识率需要用注册之外的真实谈话，以及未注册者和多人混说的录音另测。

[SpeechBrain 官方模型与样本](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) · [说话人验证 API](https://speechbrain.readthedocs.io/en/stable/API/speechbrain.inference.speaker.html)

## 在语音面板启用录音比对

在运行家庭服务的同一台机器上，把已获成员同意的注册模板放进私有目录。文件名对应真实选定的演示角色：`mother.json`、`father.json`、`child.json`，至少两位。每位用自己单独的录音注册，例如下面的两个输入路径需要换成本机音频。

```bash
export FAMILY_VOICE_PROFILES=$(mktemp -d)
python scripts/family_speaker.py --model "$FAMILY_VOICE_MODEL" enroll \
  "$FAMILY_VOICE_PROFILES/mother.json" /path/to/mother-enrollment.wav
python scripts/family_speaker.py --model "$FAMILY_VOICE_MODEL" enroll \
  "$FAMILY_VOICE_PROFILES/father.json" /path/to/father-enrollment.wav
export FAMILY_VOICE_PYTHON="$(command -v python)"
python backend/family_demo.py --port 8765
```

打开本地 App 的「语音」→「通过已注册声音查找成员」，选择待比对的 WAV 并点「比对录音」。推荐使用另一个句子。结果可能显示候选人或保留未知。查看候选后在「当前说话人」中手动选择。模板与模型配置缺失时，这个控件会隐藏，原有语音输入照常可用。

浏览器把 WAV 发给当前家庭服务，服务在本机临时目录处理，并在正常返回或可处理的异常后清理录音。支持 8–48 kHz 单声道或双声道 PCM，文件上限 12 MiB；一次只比对一段。该演示默认绑定回环地址。FastAPI 同样挂载 `GET /api/family/speaker/status` 和 `POST /api/family/speaker/identify`（原始 WAV，`Content-Type: audio/wav`）。设备控制状态不参与这两个请求。默认 Docker 镜像使用手动身份；使用声纹需另外挂载本机权重、模板并提供相应的 Python 推理环境。

网页接口仅返回候选成员或未知、判定类型和设备授权为否。逐成员相似度及阈值保留在本机命令行，用于诊断与校准。

端到端复验使用临时演示模板，在 Chrome 打开语音面板并手选「爸爸」，再上传和「妈妈」临时模板相同的公开样本。面板显示候选「妈妈」，当前说话人仍为「爸爸」。另用 FastAPI 接口验证状态前后相同，以及未配置、文件格式无效和媒体类型错误三种返回。仓库仅包含程序和操作说明。

## 浏览器接口回归

```bash
node --test scripts/family_voice.test.cjs
```

五个离线用例覆盖浏览器能力缺失、明确标注的模拟转写、中间及最终转写、麦克风错误、朗读打断和跨人物回调隔离。它们使用浏览器接口替身。真实麦克风、口音、远场噪声和浏览器语音服务需要现场验证。
