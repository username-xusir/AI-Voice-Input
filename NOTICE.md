# 第三方组件与许可

本项目代码采用 MIT 许可（见 `LICENSE`）。以下模型/依赖不包含在本项目源码中，但在运行时会使用。

## 模型

### OpenVINO int4 模型（默认使用）

- 预览：`OpenVINO/whisper-base-int4-ov` → `models/whisper-base-int4-ov`
- 快速最终：`OpenVINO/whisper-small-int4-ov` → `models/whisper-small-int4-ov`
- 高精度：`OpenVINO/whisper-large-v3-turbo-int4-ov` → `models/whisper-large-v3-turbo-int4-ov`
- 上游：OpenAI Whisper（MIT）；OpenVINO 转换/INT4 压缩工具为 Apache-2.0
- 说明：源码仓库不包含权重；GitHub Releases 的安装包会附带对应模型，许可见上。

### faster-whisper 回退：最终模型

- 名称：Whisper large-v3-turbo（faster-whisper / CTranslate2 转换版）
- 来源：`mobiuslabsgmbh/faster-whisper-large-v3-turbo`
- 上游：`openai/whisper-large-v3-turbo`
- 许可：MIT
- 本地路径：`%USERPROFILE%/.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo`
- 说明：OpenAI Whisper 模型（MIT）；源码仓库不包含权重，安装包可在 Releases 中附带。

### 快速最终模型

- 名称：Whisper small（faster-whisper / CTranslate2 转换版）
- 来源：`Systran/faster-whisper-small`
- 上游：`openai/whisper-small`
- 许可：MIT
- 本地路径：`models/faster-whisper-small`
- 校验：`model.bin` SHA256 = `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`

### 实时预览模型

- 名称：Whisper base（faster-whisper / CTranslate2 转换版）
- 来源：`Systran/faster-whisper-base`
- 上游：`openai/whisper-base`
- 许可：MIT
- 本地路径：`models/faster-whisper-base`
- 校验：`model.bin` SHA256 = `d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9`

### 旧模型（当前版本未使用）

- NVIDIA Nemotron 3.5 ASR Streaming 0.6B
- 许可：OpenMDW 1.1 — <https://openmdw.ai/license/1-1/>
- 本地路径：`models/nemotron-asr`
emotron-asr`
- 当前代码不再加载；保留仅用于回滚/对比。

## Python 依赖

| 组件 | 许可 | 用途 |
| --- | --- | --- |
| OpenVINO / OpenVINO GenAI | Apache-2.0 | Intel CPU/GPU Whisper 推理 |
| OpenCC（opencc-python-reimplemented） | Apache-2.0 | 繁体转简体 |
| faster-whisper | MIT | Whisper 推理封装（回退） |
| CTranslate2 | MIT | CPU int8 推理引擎（回退） |
| ONNX Runtime | MIT | Silero VAD（faster-whisper 内部） |
| PyAV | BSD-3-Clause | 音频解码依赖 |
| Tokenizers | Apache-2.0 | 分词 |
| Hugging Face Hub | Apache-2.0 | 模型缓存 |
| NumPy | BSD-3-Clause | 音频数组 |
| sounddevice / PortAudio | MIT | 麦克风录音 |
| soxr | LGPL-2.1+ | 重采样 |
| PySide6 / Qt | LGPL-3.0 | 桌面 UI |

完整版本锁定见 `requirements.txt`。
