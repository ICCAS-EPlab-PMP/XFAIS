# installer-payload.readable.ps1 — readable copy of the PowerShell payloads
# embedded (NSIS-escaped, $$ → $) in BETA/build/installer.nsh.
# This file is documentation only — it is NOT executed by anything.
# Keep in sync with installer.nsh when editing either side.
#
# Payload 1 (customCheckAppRunning): kill processes + purge over-long paths.
# NSIS substitutes $INSTDIR at runtime and ${PRODUCT_FILENAME}/
# ${APP_EXECUTABLE_FILENAME} at compile time.
$ErrorActionPreference = 'SilentlyContinue'
$roots = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
[void]$roots.Add('C:\Users\<user>\AppData\Local\Programs\X-FAIS'.TrimEnd('\'))
foreach ($rk in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
                'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
                'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall') {
  Get-ChildItem -LiteralPath $rk | ForEach-Object {
    $p = Get-ItemProperty -LiteralPath $_.PSPath
    if ($p.DisplayName -eq 'X-FAIS') {
      if ($p.InstallLocation) { [void]$roots.Add($p.InstallLocation.Trim().TrimEnd('\')) }
      $us = $p.UninstallString
      if ($us) {
        $us = $us.Trim()
        $q = [char]34
        if ($us.StartsWith($q)) {
          $us = $us.Substring(1)
          $i = $us.IndexOf($q)
          if ($i -ge 0) { $us = $us.Substring(0, $i) }
        }
        $d = Split-Path -Parent $us
        if ($d) { [void]$roots.Add($d.TrimEnd('\')) }
      }
    }
  }
}
$roots.Remove('') | Out-Null
$scan = {
  Get-CimInstance Win32_Process | Where-Object {
    $pe = $_.ExecutablePath
    if (-not $pe) { return $false }
    foreach ($r in $roots) {
      if ($pe.StartsWith($r + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
          $pe.Equals($r, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
  }
}
for ($i = 0; $i -lt 3; $i++) {
  $v = @(& $scan)
  if ($v.Count -eq 0) { break }
  $v | Where-Object { $_.Name -eq 'X-FAIS.exe' } | ForEach-Object {
    $gp = Get-Process -Id $_.ProcessId
    if ($gp -and $gp.MainWindowTitle) { [void]$gp.CloseMainWindow() }
  }
  Start-Sleep -Milliseconds 1800
  $v = @(& $scan)
  if ($v.Count -gt 0) {
    $v | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep -Milliseconds 900
  }
}
# Purge files whose full path is >= 255 chars: NSIS Rename (used by legacy
# uninstallers in --updated mode) cannot handle them and aborts the uninstall.
foreach ($r in $roots) {
  if (-not (Test-Path -LiteralPath $r)) { continue }
  Get-ChildItem -LiteralPath $r -Recurse -File -Force |
    Where-Object { $_.FullName.Length -ge 255 } |
    ForEach-Object { [void][System.IO.File]::Delete('\\?\' + $_.FullName) }
}
exit 0

# Payload 2 (customRemoveFiles): robocopy /MIR fallback after RMDir /r.
# NSIS substitutes $PLUGINSDIR and $INSTDIR at runtime.
#   $e = "$PLUGINSDIR\xfais-empty"
#   New-Item -ItemType Directory -Force -Path $e | Out-Null
#   robocopy $e "$INSTDIR" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
#   Remove-Item -Force -Recurse $e
