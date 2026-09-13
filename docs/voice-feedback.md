# 正确答题与高精度标注激励

普通语音只在用户提交答案、后端确定性判分返回 `correct: true` 后播放。标框或多边形题的确定性结果若 `iou > 0.90`（严格大于，不含恰好 90%），改为播放一次白色圆底、透明画布的绿色 Lottie 对钩，以及网上新下载的 1.534 秒真人男声“Congratulations!”。对钩没有黄色矩形背景、边框、阴影或彩纸。AI 导师回答和教学讲解不朗读；岗关和赛关仍在整包结算后才反馈，不借动画或语音提前透露逐题结果。

## 音色选择与来源

已查阅市场上中文神经语音的官方资料：

| 方案 | 官方提供的中文音色或能力 | 本次处理 |
| --- | --- | --- |
| 阿里云千问 TTS | `Cherry` 芊悦、`Serena` 苏瑶等中文音色；官方音色表描述芊悦偏积极亲切 | 适合后续按服务账号制作更丰富的音色包；本次没有配置或调用该付费服务。 |
| 火山引擎豆包语音 | 产品页提供小何 2.0、Vivi 2.0 等试听入口，并支持情绪表达 | 已调研，未下载其试听样本作为项目素材。 |
| Microsoft Azure Speech | 中文神经音色如 `zh-CN-XiaoxiaoNeural` | 未采用浏览器系统合成；不把第三方 `edge-tts` 客户端许可证当作音频输出授权。 |
| Kokoro-82M-v1.1-zh | 开放权重中文模型，官方提供 `zf_001` 等中文音色 | **本次实际使用**：在本机离线推理，将原创激励短句预先生成为 WAV，随应用提供。 |

官方来源：

- [阿里云 Qwen-TTS 音色列表](https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list)
- [火山引擎豆包语音产品页](https://www.volcengine.com/products/Audio-editing-and-sound-processing)
- [Azure Speech 语言与音色支持](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)
- [Microsoft Azure 产品条款](https://www.microsoft.com/licensing/terms/en-US/productoffering/MicrosoftAzure/EAEAS)：付费层 TTS 的预置神经音色输出使用权有单独约定。
- [Kokoro 中文模型官方说明](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh)：标注 Apache-2.0，说明中文专业数据由龙猫数据授权提供。
- [Kokoro 官方生成实现](https://github.com/hexgrad/kokoro)

普通鼓励包是 AI 合成语音，没有模仿指定个人；选用 `zf_001` 普通话女声，语速 1.05，短句轮换。精准标注的专用音频另选公开授权的真人男声录音，和普通鼓励音色分开。

## 随项目提供的文件

`public/audio/encouragement/` 中包含六句 24kHz、单声道、PCM 16-bit WAV：

1. 答对啦，做得很好！
2. 很棒，继续保持！
3. 漂亮，这一题完成得很棒！
4. 答对了，给自己点个赞！
5. 做得不错，继续加油！
6. 太棒了，下一题继续！

`manifest.json` 记录模型固定版本、模型和音色 SHA-256、生成依赖版本、语速、采样率、每句文案、文件校验值、解码后时长和音量统计。`KOKORO-LICENSE.txt` 保留上游 Apache-2.0 许可证。模型下载和推理仅用于制作素材，运行平台不需要 PyTorch、模型文件、TTS 服务、API 密钥或外网语音请求。

高精度标注另提供：

- `public/animations/success-checkmark.json`：由已经下载的 [Success Confetti](https://lottiefiles.com/free-animation/success-confetti-mX0p5zY7XU)（Ismail Tofey (AUX)）派生。只保留原对钩路径与两个变换图层，实际删除背景矩形、圆形和彩纸图层；对钩改为绿色并居中，播放第 19–110 帧。原 `success-confetti.json` 留作可重建的来源文件，不再由播放器加载。`manifest.json` 记录原文件/派生文件 SHA-256 和修改方式，`LICENSE.txt` 保留同一 Lottie Simple License。
- `public/audio/precision/congratulations.wav`：2026-09-13 从 [Kenney 官方 Voiceover Pack](https://kenney.nl/assets/voiceover-pack) 新下载的 `Male/congratulations.ogg` 转成 WAV，真人配音者为 Jeffrey M. Smith。保留整句、原采样率 44.1kHz 和音高，仅将峰值统一至 -3dB，不合成、不混入 Kokoro 或旧提示音。浏览器运行时只读取随项目提供的本地 WAV。
- 原作者以 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) 提供该语音包，允许复制、修改和分发，包括商业项目。目录中的 `KENNEY-LICENSE.txt` 与 `CREDITS.txt` 保留下载包自带的许可和演员署名；`manifest.json` 固定官方下载地址、ZIP SHA-256、原 OGG SHA-256、最终 WAV SHA-256、时长及音量。该素材使用不表示作者为本平台背书。

## 播放器约定

播放器在 `src/audio.ts`，仅加载同源本地 WAV，用 Web Audio 播放。Web Audio 是音频文件播放器，不会调用浏览器的文字转语音或系统音色。

- `unlockEncouragementAudio()`：在提交、开始训练或开启声音的用户点击事件内立即调用，须在等待 API 前调用。只恢复音频权限和预加载，不播放问候或讲解。
- `playEncouragement()`：仅在后端确认正确后调用，按顺序轮换短句。返回 `played`、`muted`、`unavailable` 或 `cancelled`，结果不参与判分。
- `playPrecisionReward()`：只加载同源 `congratulations.wav`，由页面在标注结果 `iou > 0.90` 后调用；与普通语音共用单通道，避免重叠播放。
- `setEncouragementEnabled(boolean)`：同步当前账号的声音偏好；关闭时立即停止。账号偏好由既有用户 API 持久化，播放器不创建跨账号的 localStorage 开关。
- `stopEncouragementAudio()`：离开答题页、切题、退出账号时使用；同时取消尚在下载/解码的播放请求，防止旧页面延迟响起。

只保留一个播放通道，新的激励会停止上一句。加载、解码或权限失败时不使用系统合成兜底，原有文字判分与激励继续显示，不影响保存答案和下一题。

## 重新生成

日常启动不执行以下命令。只有修改文案或音色才需要可联网的制作环境：

```powershell
uv venv .runtime/voice-build --python .venv/Scripts/python.exe
uv pip install --python .runtime/voice-build/Scripts/python.exe torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .runtime/voice-build/Scripts/python.exe kokoro==0.9.4 'misaki[zh]==0.9.4' soundfile==0.13.1 'transformers>=4.48,<4.52'
.runtime/voice-build/Scripts/python.exe -X utf8 scripts/build_encouragement_audio.py
```

制作脚本固定模型仓库版本 `01e7505bd6a7a2ac4975463114c3a7650a9f7218`，核对发布方给出的模型 SHA-256，使用 CPU 和固定 seed 42。模型文件存放在 `.runtime/voice-model/`，不放进 `public/`。输出裁去冗长的首尾静音、保留 80ms 余量、统一峰值到 -3dB，不改变音高。各文件写入后通过 soundfile 重新解码并检查时长、采样率和非静音；浏览器实际播放验收应另行记录，不能用文件生成成功代替。

精准标注素材的准备脚本独立于普通鼓励模型，只需要 Python、numpy 和 soundfile：

```powershell
.runtime/voice-build/Scripts/python.exe -X utf8 scripts/build_precision_reward.py
```

脚本下载并校验固定的 Kenney ZIP，提取真人男声、转码并重新解码验证，再从已有 Lottie 原文件重建无背景对钩。源 ZIP 只缓存在 `.runtime/reward-source/`。无需下载或运行 Kokoro 模型；日常启动也不执行该脚本。

## 本次验证证据

- 六个 WAV 已全部生成并经 soundfile 实际重新解码；总计 540,596 字节，每句 1.52–2.23 秒。具体 SHA-256、时长、音量见音频目录的 `manifest.json`。
- `npm run build`：Vue/TypeScript 检查和生产构建通过，构建中包含六个真实音频文件。
- `node scripts/verify_encouragement_audio.mjs`：**21 项通过**，记录在 `docs/voice-playback-tests.json`。除原有用户手势、轮换、单通道、静音与异步生命周期外，还检查新真人 WAV 的真实字节、CC0 清单及与普通语音哈希不同，Lottie 只有一个可绘制的对钩路径且没有背景图层，专用播放路径，以及恰好 90% 不触发、90.1% 触发的严格阈值。
- 组件回归确认：提交时保存题 ID 与答案快照，保存期间不允许切题；退出或切换训练后，旧判分响应不播放声音、不写入新题反馈；播放完成状态不写到其他题。新手步骤切换同步停止声音，正确提交仍能在进入反馈步骤后播放。

状态机验证用可控的 Web Audio/API 替身检查竞态，真实音频解码由 soundfile 检查，二者不冒充浏览器实播或主观试听。浏览器页面交互与播放状态由本轮主验收另外验证。
