Unicode true
!include "MUI2.nsh"
!include "Sections.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define APP_NAME "Voxa"
!define APP_EXE "Voxa.exe"
!define APP_VERSION "0.7.1"
!define APP_PUBLISHER "Voxa"
!define APP_ID "Voxa"
!define SEC_CORE_ID 0
!define SEC_LARGE_ID 1

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

VIProductVersion "0.7.1.0"
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
!define MUI_WELCOMEPAGE_TEXT "Voxa 是一个完全本地的语音输入工具，声音不会离开这台电脑。$\r$\n$\r$\n安装后 Voxa 接管 Win+H：按一下开始，停止说话约 1.8 秒自动输入并关闭。系统自带语音输入不会弹出。$\r$\n$\r$\n基础安装包含 OpenVINO 运行时、base 预览模型、small 最终模型和 OpenAI large-v3-turbo 高精度模型（默认勾选，性能弱的电脑可取消）。"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "启动 Voxa（Win+H）"
!define MUI_FINISHPAGE_TEXT "安装完成。$\r$\n$\r$\nVoxa 已在后台运行，按 Win+H 开始说话；停止说话约 1.8 秒自动生成。$\r$\n$\r$\n点击托盘图标可打开设置：主题、CPU/GPU、静音时长、自动标点等。"

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
  ; OpenAI large model is optional and unchecked by default.
  SectionSetFlags ${SEC_LARGE_ID} ${SF_SELECTED}
FunctionEnd

Section "Voxa 主程序与基础模型（必需）" SEC_CORE
  SectionIn RO

  ; Stop both the new app and a pre-rename VoiceIn build before replacing
  ; files. Otherwise the old build keeps the Win+H hook and the new build
  ; cannot take over.
  nsExec::ExecToLog 'taskkill /IM ${APP_EXE} /F'
  nsExec::ExecToLog 'taskkill /IM VoiceIn.exe /F'

  ; Upgrade from VoiceIn: run its per-user uninstaller, then clean leftovers.
  IfFileExists "$LOCALAPPDATA\Programs\VoiceIn\Uninstall.exe" 0 legacy_done
    DetailPrint "正在移除旧版 VoiceIn…"
    nsExec::ExecToLog '"$LOCALAPPDATA\Programs\VoiceIn\Uninstall.exe" /S'
    Sleep 1200
  legacy_done:
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "VoiceIn"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceIn"
  DeleteRegKey HKCU "Software\VoiceIn"
  Delete "$DESKTOP\声入.lnk"
  RMDir /r "$SMPROGRAMS\声入"

  SetOutPath "$INSTDIR"
  File /r "..\dist\Voxa\*.*"
  File "..\README.md"
  File "..\LICENSE"
  File "..\NOTICE.md"

  CreateDirectory "$LOCALAPPDATA\Voxa"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

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
SectionEnd

Section "OpenAI Whisper large-v3-turbo 高精度模型（默认包含）" SEC_LARGE
  SetOutPath "$INSTDIR\models\whisper-large-v3-turbo-int4-ov"
  File /r "..\dist\models-large\whisper-large-v3-turbo-int4-ov\*.*"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_CORE_ID} "必需：Voxa 主程序、OpenVINO 运行时、Whisper base 预览模型、Whisper small 最终模型。默认 CPU 推理，启动约 6 秒。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_LARGE_ID} "默认勾选：OpenAI Whisper large-v3-turbo int4 高精度模型（约 480 MB）。在普通笔记本 CPU 上一句可能 10–20 秒；不需要可取消。安装后设置里的“高精度模型”开关才可用。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  nsExec::ExecToLog 'taskkill /IM ${APP_EXE} /F'

  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_ID}"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
  DeleteRegKey HKCU "Software\Voxa"

  Delete "$DESKTOP\Voxa.lnk"
  RMDir /r "$SMPROGRAMS\Voxa"

  ; Remove the application and bundled models. User settings/logs in
  ; %LOCALAPPDATA%\Voxa are intentionally kept.
  RMDir /r "$INSTDIR"
SectionEnd
