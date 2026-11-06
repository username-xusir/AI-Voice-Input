# 构建与发布 — Voxa 0.7.2

## 依赖

```bat
uv pip install --python .venv\Scripts\python.exe pyinstaller pillow
```

NSIS 使用 `tools/nsis/nsis-3.11/Bin/makensis.exe`（需自行下载，不随项目提交）。

> `build/`、`dist/`、`release/*.exe`、`.venv/`、`ov_cache/` 都是本地产物，已由 `.gitignore` 忽略；不要提交到仓库。安装包通过 GitHub Releases 分发。

## 1. 构建程序目录

```bat
.venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\Voxa.spec
```

产物：`dist\Voxa\Voxa.exe` + `dist\Voxa\_internal\`。

## 2. 放模型

基础安装（必需）：

```text
dist\Voxa\models\whisper-base-int4-ov\
dist\Voxa\models\whisper-small-int4-ov\
```

可选高精度：

```text
dist\models-large\whisper-large-v3-turbo-int4-ov\
```

模型来源：

- `OpenVINO/whisper-base-int4-ov`
- `OpenVINO/whisper-small-int4-ov`
- `OpenVINO/whisper-large-v3-turbo-int4-ov`

## 3. 编译安装包

```bat
tools\nsis\nsis-3.11\Bin\makensis.exe packaging\installer.nsi
```

产物：`release\Voxa-Setup-0.7.2.exe`。

安装包特性：

- 安装到 `%LOCALAPPDATA%\Programs\Voxa`，无需管理员权限。
- 组件页：基础模型必需；OpenAI large 高精度模型默认勾选，性能弱的电脑可取消。
- 检测到旧版 VoiceIn 时，先静默运行旧卸载器，清理旧版 Run 项、开始菜单和桌面快捷方式。
- 写入 HKCU Run 开机自启动；创建 Voxa 开始菜单/桌面快捷方式。
- 应用启动时把旧版 `%LOCALAPPDATA%\VoiceIn\config.json` 迁移到 `%LOCALAPPDATA%\Voxa`，并把模型路径规范到新安装目录。
- 卸载器删除程序/模型/快捷方式/自启动，保留 `%LOCALAPPDATA%\Voxa` 配置与日志。

## 4. 验证

1. 在临时目录静默安装：

   ```bat
   release\Voxa-Setup-0.7.2.exe /S /D=C:\temp\VoxaTest
   ```

2. 启动 `C:\temp\VoxaTest\Voxa.exe`，等托盘就绪。
3. 按 Win+H 说一句话，停止说话约 1.8 秒，确认自动输入且浮窗保持打开；点 × 才关闭。
4. 录音时确认浮窗麦克风变成动态声波。
5. 浮窗“设置”打开快速设置；托盘左键打开详细设置，确认两者不同且不弹语音浮窗。
6. 设置里切换 CPU/GPU，确认状态提示并在加载完成后可继续识别。
7. 再次双击 `Voxa.exe`，确认已有实例只打开详细设置，不弹出语音浮窗。
8. 检查 `%LOCALAPPDATA%\Voxa\logs\app.log`。
9. 运行 `C:\temp\VoxaTest\Uninstall.exe /S`，确认程序/模型/快捷方式/自启动被清理。

## 5. GitHub Release

上传：

- `release\Voxa-Setup-0.7.2.exe`
- `release\SHA256SUMS.txt`
- `release\RELEASE_NOTES.md`

建议 Release 说明包含：

- 版本、Windows 11、CPU 要求。
- 安装包默认包含基础模型与 large 高精度模型；large 可取消。
- Win+H 接管说明。
- 0.7.2 浮窗常驻结果、快速/详细设置分离、桌面入口不弹语音浮窗。
- 已知限制：高精度慢、实时输入依赖光标、Iris Xe GPU 更慢。
