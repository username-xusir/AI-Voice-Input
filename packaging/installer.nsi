Unicode true
!include "MUI2.nsh"
!include "Sections.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define APP_NAME "Voxa"
!define APP_EXE "Voxa.exe"
!define APP_VERSION "0.7.6"
!define APP_PUBLISHER "Voxa"
!define APP_ID "Voxa"
!define SEC_CORE_ID 0
!define SEC_LARGE_ID 1
!define INSTALL_LOG "$TEMP\Voxa-install.log"

!macro LOG_STEP text
  FileOpen $9 "${INSTALL_LOG}" a
  FileSeek $9 0 END
  FileWrite $9 "${text}$\r$\n"
  FileClose $9
!macroend

Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\release\Voxa-Setup-${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\Voxa"
InstallDirRegKey HKCU "Software\Voxa" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
BrandingText "Voxa · 本地语音输入"
Icon "app.ico"
UninstallIcon "app.ico"

VIProductVersion "0.7.6.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileDescription" "Voxa 本地语音输入安装程序"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "LegalCopyright" "MIT License"

!define MUI_ABORTWARNING
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!define MUI_WELCOMEPAGE_TITLE "安装 Voxa"
!define MUI_WELCOMEPAGE_TEXT "Voxa 是一个完全本地的语音输入工具，声音不会离开这台电脑。$\r$\n$\r$\n安装后 Voxa 接管 Win+H：按一下开始，停止说话约 1.8 秒自动输入，浮窗保持打开。系统自带语音输入不会弹出。$\r$\n$\r$\n基础安装包含 OpenVINO 运行时、Whisper Tiny 最小模型和 Whisper Small 均衡模型；另有 large-v3-turbo 最大模型可选（默认勾选，性能弱的电脑可取消）。三档都是多语言模型。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "启动 Voxa（Win+H）"
!define MUI_FINISHPAGE_TEXT "安装完成。$\r$\n$\r$\nVoxa 已在后台运行，按 Win+H 开始说话；停止说话约 1.8 秒自动生成并上屏，浮窗保持打开。$\r$\n$\r$\n点击托盘图标可打开详细设置：主题、CPU/GPU、静音时长、自动标点等；浮窗“设置”打开快速设置。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  FileOpen $9 "${INSTALL_LOG}" w
  FileWrite $9 "Voxa installer ${APP_VERSION} start$\r$\n"
  FileWrite $9 "EXEPATH=$EXEPATH$\r$\n"
  FileWrite $9 "INSTDIR=$INSTDIR$\r$\n"
  FileClose $9

  ; OpenAI large model is optional and unchecked by default.
  SectionSetFlags ${SEC_LARGE_ID} ${SF_SELECTED}
FunctionEnd

Section "Voxa 主程序与基础模型（必需）" SEC_CORE
  SectionIn RO

  ; Stop both the new app and a pre-rename VoiceIn build before replacing
  ; files. Exclude this installer's own PID: if the setup file was renamed
  ; to Voxa.exe, a plain "taskkill /IM Voxa.exe" would kill the installer
  ; itself right after the progress bar appears.
  System::Call 'kernel32::GetCurrentProcessId() i .r0'
  !insertmacro LOG_STEP "core: start pid=$0"
  DetailPrint "正在停止旧版 Voxa…"
  nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE} /FI "PID ne $0"'
  !insertmacro LOG_STEP "core: after taskkill Voxa"
  DetailPrint "正在停止旧版 VoiceIn…"
  nsExec::ExecToLog 'taskkill /F /IM VoiceIn.exe /FI "PID ne $0"'
  !insertmacro LOG_STEP "core: after taskkill VoiceIn"

  ; Upgrade from VoiceIn: run its per-user uninstaller, then clean leftovers.
  IfFileExists "$LOCALAPPDATA\Programs\VoiceIn\Uninstall.exe" 0 legacy_done
    DetailPrint "正在移除旧版 VoiceIn…"
    !insertmacro LOG_STEP "core: run legacy VoiceIn uninstaller"
    nsExec::ExecToLog '"$LOCALAPPDATA\Programs\VoiceIn\Uninstall.exe" /S'
    Sleep 1200
  legacy_done:
  !insertmacro LOG_STEP "core: legacy cleanup"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "VoiceIn"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceIn"
  DeleteRegKey HKCU "Software\VoiceIn"
  Delete "$DESKTOP\声入.lnk"
  RMDir /r "$SMPROGRAMS\声入"

  SetOutPath "$INSTDIR"
  DetailPrint "正在解压程序文件…"
  !insertmacro LOG_STEP "core: before File /r"
  File /r "..\dist\Voxa\*.*"
  !insertmacro LOG_STEP "core: after File /r"
  File "..\README.md"
  File "..\LICENSE"
  File "..\NOTICE.md"

  ; Remove the old base preview model only after the new files are in place.
  ; Deleting it before extraction made an early installer crash much harder
  ; to recover from and is unnecessary during the copy.
  DetailPrint "正在清理旧版 base 预览模型…"
  !insertmacro LOG_STEP "core: before remove old base"
  RMDir /r "$INSTDIR\models\whisper-base-int4-ov"
  !insertmacro LOG_STEP "core: after remove old base"

  CreateDirectory "$LOCALAPPDATA\Voxa"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  !insertmacro LOG_STEP "core: wrote uninstaller"

  CreateDirectory "$SMPROGRAMS\Voxa"
  CreateShortcut "$SMPROGRAMS\Voxa\Voxa.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\Voxa\卸载 Voxa.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\Voxa.lnk" "$INSTDIR\${APP_EXE}"

  ; Autostart (also ensured by the app itself).
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_ID}" '"$INSTDIR\${APP_EXE}" --silent'

  WriteRegStr HKCU "Software\Voxa" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoRepair" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "EstimatedSize" 1400000
  !insertmacro LOG_STEP "core: done"
SectionEnd

Section "OpenAI Whisper large-v3-turbo 最大模型（默认包含）" SEC_LARGE
  !insertmacro LOG_STEP "large: before File /r"
  SetOutPath "$INSTDIR\models\whisper-large-v3-turbo-int4-ov"
  File /r "..\dist\models-large\whisper-large-v3-turbo-int4-ov\*.*"
  !insertmacro LOG_STEP "large: done"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_CORE_ID} "必需：Voxa 主程序、OpenVINO 运行时、Whisper Tiny 最小模型（约 40 MB）和 Whisper Small 均衡模型（约 155 MB）。三档模型都支持多语言；默认 CPU 推理。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_LARGE_ID} "默认勾选：OpenAI Whisper large-v3-turbo int4 最大模型（约 456 MB）。普通笔记本 CPU 上一句可能 10–20 秒；不需要可取消。安装后详细设置里的“最终模型 → 最大”才可用。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  System::Call 'kernel32::GetCurrentProcessId() i .r0'
  !insertmacro LOG_STEP "uninstall: start pid=$0"
  nsExec::ExecToLog 'taskkill /F /IM ${APP_EXE} /FI "PID ne $0"'

  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_ID}"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
  DeleteRegKey HKCU "Software\Voxa"

  Delete "$DESKTOP\Voxa.lnk"
  RMDir /r "$SMPROGRAMS\Voxa"

  ; Remove the application and bundled models. User settings/logs in
  ; %LOCALAPPDATA%\Voxa are intentionally kept.
  RMDir /r "$INSTDIR"
SectionEnd
