; installer.nsh — custom NSIS macros for the X-FAIS installer
; ============================================================================
; 根因（2026-09-21 实证）：应用内「一键安装依赖」会把 PySide6 pip 进
; resources\python-runtime，其中 qml\...\objects-*\ 下的构建残留会造出
; ≥260 字符的文件路径。electron-builder 卸载器在 --updated 模式（覆盖安装
; 时必走）用 NSIS Rename 逐文件把 $INSTDIR 原子改名进 $PLUGINSDIR，而
; Rename 不带 \\?\ 前缀、无法处理超长路径 → 中途 Abort(exit 2) →
; uninstallOldVersion 重试 5 次全部失败 → 用户看到「无法关闭 X-FAIS /
; 卸载失败」→ 覆盖安装永远失败（即「程序打开无法安装」的真实来源）。
;
; Root cause (proven 2026-09-21): the in-app dependency installer pip-installs
; PySide6 into resources\python-runtime, whose qml build artifacts create file
; paths ≥ 260 chars. The electron-builder uninstaller in --updated mode (always
; used when reinstalling over an existing install) renames every file out of
; $INSTDIR with NSIS Rename — which cannot handle paths past MAX_PATH — so it
; aborts with exit 2, uninstallOldVersion retries 5×, and the user is shown
; "app cannot be closed / uninstall failed" on every upgrade.
;
; 本文件的三个宏（缺一不可 / all three required）：
;   customCheckAppRunning        — 安装/卸载前：多根目录清进程 + 预删超长
;                                  路径文件（让用户机器上【旧版】卸载器也能成功）
;   customRemoveFiles            — 卸载时：用 RMDir /r + robocopy 兜底取代
;                                  electron-builder 的 atomicRMDir 改名路径
;   customUnInstallCheck[_CurrentUser] — 旧版卸载器万一仍失败：继续安装而不
;                                  是弹「卸载失败」中止
; A readable copy of the PowerShell payloads lives next to this file in
; installer-payload.readable.ps1. 改动时两处同步改，并重跑打包验证。
; ============================================================================

!macro customCheckAppRunning
  DetailPrint "Closing ${PRODUCT_FILENAME}, stale runtime processes, purging over-long paths..."
  ; Kill every process running from $INSTDIR or any registered install dir
  ; (graceful close first, then force), then delete files whose full path is
  ; >= 255 chars — those break the old uninstaller's NSIS Rename pass.
  nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "$$ErrorActionPreference='SilentlyContinue';$$roots=[System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase);[void]$$roots.Add('$INSTDIR'.TrimEnd('\'));foreach($$rk in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'){Get-ChildItem -LiteralPath $$rk|ForEach-Object{$$p=Get-ItemProperty -LiteralPath $$_.PSPath;if($$p.DisplayName -eq '${PRODUCT_FILENAME}'){if($$p.InstallLocation){[void]$$roots.Add($$p.InstallLocation.Trim().TrimEnd('\'))};$$us=$$p.UninstallString;if($$us){$$us=$$us.Trim();$$q=[char]34;if($$us.StartsWith($$q)){$$us=$$us.Substring(1);$$i=$$us.IndexOf($$q);if($$i -ge 0){$$us=$$us.Substring(0,$$i)}};$$d=Split-Path -Parent $$us;if($$d){[void]$$roots.Add($$d.TrimEnd('\'))}}}}};$$roots.Remove('')|Out-Null;$$scan={Get-CimInstance Win32_Process|Where-Object{$$pe=$$_.ExecutablePath;if(-not $$pe){return $$false};foreach($$r in $$roots){if($$pe.StartsWith($$r+'\',[System.StringComparison]::OrdinalIgnoreCase) -or $$pe.Equals($$r,[System.StringComparison]::OrdinalIgnoreCase)){return $$true}};return $$false}};for($$i=0;$$i -lt 3;$$i++){$$v=@(& $$scan);if($$v.Count -eq 0){break};$$v|Where-Object{$$_.Name -eq '${APP_EXECUTABLE_FILENAME}'}|ForEach-Object{$$gp=Get-Process -Id $$_.ProcessId;if($$gp -and $$gp.MainWindowTitle){[void]$$gp.CloseMainWindow()}};Start-Sleep -Milliseconds 1800;$$v=@(& $$scan);if($$v.Count -gt 0){$$v|ForEach-Object{Stop-Process -Id $$_.ProcessId -Force};Start-Sleep -Milliseconds 900}};foreach($$r in $$roots){if(Test-Path -LiteralPath $$r){Get-ChildItem -LiteralPath $$r -Recurse -File -Force|Where-Object{$$_.FullName.Length -ge 255}|ForEach-Object{[void][System.IO.File]::Delete('\\?\' + $$_.FullName)}}};exit 0"`
  Pop $0
  ; Fallback for machines where PowerShell is blocked: kill the app tree by
  ; name (also reaches the portable copy and orphaned children).
  nsExec::Exec `"$SYSDIR\taskkill.exe" /IM "${APP_EXECUTABLE_FILENAME}" /T /F`
  Pop $0
!macroend

!macro customRemoveFiles
  ; Replace electron-builder's isUpdated atomic-rename (un.atomicRMDir): its
  ; per-file NSIS Rename cannot handle >=260-char paths and aborts the whole
  ; uninstall. Plain recursive delete handles them, with a robocopy /MIR pass
  ; as a long-path-safe fallback for anything RMDir leaves behind.
  ; 替代 electron-builder 的 isUpdated 原子改名路径：逐文件 Rename 处理
  ; 不了 ≥260 字符的路径并整体 Abort。直接递归删除 + robocopy 兜底。
  SetOutPath $TEMP
  RMDir /r $INSTDIR
  ${If} ${FileExists} "$INSTDIR\*.*"
    DetailPrint "RMDir left residue, using robocopy /MIR fallback..."
    nsExec::Exec `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "$$e='$PLUGINSDIR\xfais-empty';New-Item -ItemType Directory -Force -Path $$e|Out-Null;robocopy $$e '$INSTDIR' /MIR /NFL /NDL /NJH /NJS /NP|Out-Null;Remove-Item -Force -Recurse $$e"`
    Pop $0
    RMDir /r $INSTDIR
  ${EndIf}
!macroend

; handleUninstallResult calls these before showing "uninstall failed" and
; aborting the whole install. Legacy uninstallers already in the field may
; still fail for reasons we cannot patch retroactively — log nothing and let
; the install continue; the new files overwrite the old tree anyway.
; 覆盖安装时旧版卸载器若仍失败（无法追溯修复），不再中止安装，直接继续，
; 新文件会覆盖旧目录。
!macro customUnInstallCheck
!macroend

!macro customUnInstallCheckCurrentUser
!macroend
