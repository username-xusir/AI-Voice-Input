# Voxa · 本地语音输入

Voxa 是 Windows 11 的本地语音输入浮窗。它接管 **Win+H**：按一下开始，边说边输入，停止说话后自动生成并关闭。声音不上传，完全离线。

- **默认后端**：OpenVINO GenAI int4 Whisper
- **实时预览**：`whisper-base-int4-ov`（约 0.8–1.5 秒一次）
- **最终校正**：`whisper-small-int4-ov`（约 3–5 秒）
- **高精度**：`whisper-large-v3-turbo-int4-ov`（默认打包，CPU 约 10–20 秒）
- **回退**：OpenVINO 不可用时自动使用 faster-whisper / CTranslate2

## 功能

- **Win+H 接管**：长按也只触发一次，不会弹出微软原生语音输入。
- **边说边输入**：实时预览直接写入当前输入框；停止时只修正变化的尾部。
- **自动结束**：停止说话约 1.8 秒后自动生成、自动上屏、自动关闭；可在设置里调静音时长。
- **麦克风声波**：录音时圆形按钮变成跟随实际音量的动态声波；停止后恢复麦克风图标。
- **主题**：默认青色；浅色是独立的白/灰配色，深色是独立的炭黑配色，按钮、开关、图标都随主题整套切换，不混用青色。
- **自动标点**：可开关。开：保留 Whisper 的逗号/句号；关：去掉标点。
- **计算设备**：设置里可选 CPU / GPU；切换后自动重载模型，失败自动保留原设备。
- **设置入口**：浮窗上的“设置”、托盘左键/双击、托盘菜单“打开设置”，或再次双击桌面快捷方式。
- **其他**：实时预览、自动上屏、识别语言、高精度模型、开机自启动、暂停热键。
- **托盘静默运行**：默认开机自启动，只留托盘图标。

> 在 Intel Iris Xe 核显上实测 OpenVINO GPU 比 CPU 慢，因此默认 CPU；设置里保留 GPU 选项，方便换到独显机器使用。

## 交互

1. 在输入框里按一下 **Win+H**：浮窗出现，开始录音，实时预览会把文字输入当前输入框。
2. **停止说话约 1.8 秒**：自动停止录音、跑最终校正、上屏并关闭；不需要确认键。
3. 录音中 **点麦克风**：暂停，浮窗保留；再点一次继续。
4. **按 Win+H / Esc**：提前结束。最终校正中再按 Esc：取消本次校正并关闭。
5. 浮窗可以**拖动**。
6. 点 **设置** 打开完整设置卡片；点 **×** 结束并关闭。
7. 托盘左键/双击：打开设置。再次启动 `Voxa.exe`（如双击桌面快捷方式）也会打开已有实例的设置，而不是报“已在运行”；首次手动启动也会直接打开设置。

## 安装包（推荐）

`Voxa-Setup-0.7.1.exe`（从 GitHub Releases 下载）

- 安装到当前用户目录 `%LOCALAPPDATA%\Programs\Voxa`，不需要管理员权限。
- 自带 OpenVINO 运行时、Whisper base 预览模型、Whisper small 最终模型。
- 组件页包含 `OpenAI Whisper large-v3-turbo 高精度模型`，**默认勾选并安装**；性能弱的电脑可以在组件页取消。
- 安装时自动停止并移除旧版 VoiceIn，清理旧版自启动/快捷方式；旧配置会迁移到 `%LOCALAPPDATA%\Voxa`。
- 默认开机自启动，后台静默运行，只留托盘。
- 卸载：Windows 设置 → 应用 → **Voxa**，或开始菜单“卸载 Voxa”。

安装包不放进 git：在 GitHub Releases 上传安装包、`SHA256SUMS.txt` 和 `RELEASE_NOTES.md`。

## 源码安装 / 启动

```bat
setup.bat
```

它会创建 `.venv` 并安装 `openvino-genai`、`faster-whisper`、`ctranslate2`、`PySide6`、`sounddevice` 等依赖。

- `run.bat`：无控制台启动。
- `run-console.bat`：带控制台，日志同时写到 `logs/app.log`。

源码版配置在项目根目录 `config.json`，日志在 `logs/`；安装版配置和日志在 `%LOCALAPPDATA%\Voxa\`。

## 设置

| 设置 | 说明 |
| --- | --- |
| 自动标点 | 开：保留识别出的标点；关：去掉标点 |
| 实时预览 | 边说边把预览文字输入当前输入框 |
| 自动上屏 | 结束后用最终结果校正预览文字；关闭则只复制最终文字到剪贴板 |
| 高精度模型 | 使用 large-v3-turbo；更准但更慢，未安装时不可用 |
| 计算设备 | `CPU` 或 `GPU`；切换会重新加载模型 |
| 识别语言 | 中文 / EN / 自动 |
| 停止说话自动结束 | 是否启用静音检测自动结束 |
| 静音判定 | 0.8–4.0 秒，默认 1.8 秒 |
| 主题 | 青色（原配色）/ 浅色（白灰）/ 深色（炭黑） |
| 开机自启动 | 写入 HKCU Run，无管理员权限 |

设置会自动保存到 `config.json`，不需要“保存”按钮。设置页顶部应显示 `详细设置 · 本地语音输入 · v0.7.1`；如果看到 166×244 的旧小卡片，说明打开的是旧版 VoiceIn。

## 常用配置字段

| 字段 | 说明 |
| --- | --- |
| `hotkey` | `win+h`（默认，接管系统语音输入）；`ctrl+h` 可避开系统 |
| `ov_device` | `CPU`（默认）或 `GPU` |
| `auto_punctuation` | 自动标点，默认 `true` |
| `theme` | `teal` / `light` / `dark` |
| `auto_stop` | 停止说话后是否自动结束，默认 `true` |
| `auto_stop_silence_ms` | 静音多久自动结束，默认 `1800` 毫秒 |
| `auto_speech_level` | 说话音量阈值，默认 `0.08` |
| `auto_min_speech_ms` | 至少说多久才允许自动结束，默认 `250` 毫秒 |
| `live_preview` | 实时预览并输入，默认 `true` |
| `auto_paste` | 最终结果自动上屏，默认 `true` |
| `language` | `zh` / `en` / `auto` |
| `autostart` | 开机自启动，默认 `true` |
| `max_record_seconds` | 单次最长录音，默认 60 秒 |
| `input_device` | 麦克风设备名或索引；`null` 用系统默认 |
| `num_threads` | CPU 线程数，默认 4 |
| `native_fallback_hotkey_enabled` | 是否保留 Ctrl+Alt+H 调原生语音输入 |

## 模型

默认使用 OpenVINO int4 转换版：

- 预览：`OpenVINO/whisper-base-int4-ov`（约 64 MB）
- 最终：`OpenVINO/whisper-small-int4-ov`（约 162 MB）
- 高精度：`OpenVINO/whisper-large-v3-turbo-int4-ov`（约 478 MB）

faster-whisper 模型仅作为回退，不再参与默认推理。

源码版默认从项目根 `models/` 读取模型（目录名见上）；也可以用环境变量 `VOXA_MODEL_ROOT` 指向其他模型根目录。安装版模型在安装目录的 `models/` 下。

## 调试

- `VOICEIN_TEST_WAV=路径`：用 16 kHz 单声道 WAV 代替麦克风。
- `VOICEIN_DEBUG_STACKS=1`：每 30 秒写线程栈到 `logs/traceback.log`。
- UI 截图：运行 `scripts/test_ui.py` 生成到 `tests/`（已被 `.gitignore` 忽略）。
- 主题独立性测试：`.venv\Scripts\python.exe scripts\test_themes.py`。
- 流程测试：`QT_QPA_PLATFORM=offscreen .venv\Scripts\python.exe scripts/test_app_flow.py`。

## 已知限制

- **实时输入依赖光标**：录音期间不要移动光标或改选区，否则退格/补字会作用到新位置。
- **切换应用会暂停实时输入**：目标不在前台时不再抢焦点；结束时最终文字会复制到剪贴板。
- **自动结束会被停顿触发**：说完后约 1.8 秒没声音就生成；说话中间长停顿可能提前结束，可在设置里调大静音判定。
- **高精度较慢**：large 在普通 CPU 上一句约 10–20 秒，默认关闭。
- **GPU 不一定更快**：Intel Iris Xe 核显实测比 CPU 慢；独显机器可自行切换。
- **全屏独占应用**：可能盖住置顶浮窗，退出全屏即可。
- 低权限钩子收不到管理员应用里的按键；需要时以管理员身份启动。
- 极少数不接收 Unicode 字符的应用可能无法实时上屏，停止时会回退到剪贴板。
- 安装包未签名，SmartScreen 可能提示“未知发布者”。

## 目录

```text
app/
  main.py      入口、状态机、托盘、热键、模型热切换
  ui.py        浮窗、声波麦克风、设置卡片、三套主题、托盘
  hotkey.py    Win+H / Ctrl+H 低级键盘钩子
  recorder.py  麦克风录音、暂停/继续、实时快照
  asr.py       OpenVINO 优先 + faster-whisper 回退、VAD、繁转简、标点处理
  ov_asr.py    OpenVINO GenAI ASR 管道封装、设备检测
  injector.py  剪贴板/Unicode 文字输入、实时差异补字
  config.py    配置、日志、旧版配置迁移
scripts/       自测脚本
tests/         测试音频 fixtures
packaging/     PyInstaller spec、NSIS 安装器、构建说明
release/       发布说明与校验（安装包本体在仓库外）
```
