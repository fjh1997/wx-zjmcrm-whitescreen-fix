# 非提升启动（若失败请用 run_pb_admin.ps1）
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $Root "proxybridge.log"
"start $(Get-Date -Format o)" | Set-Content $log

Get-Process ProxyBridge_CLI, ProxyBridge -ErrorAction SilentlyContinue | ForEach-Object {
  try { Stop-Process -Id $_.Id -Force; "killed $($_.ProcessName) $($_.Id)" | Add-Content $log } catch {}
}
Start-Sleep 1

$exe = "C:\Program Files\ProxyBridge\ProxyBridge_CLI.exe"
$args = @(
  "--proxy", "http://127.0.0.1:8888",
  "--rule", "Weixin.exe;WeChatAppEx.exe:*:*:TCP:PROXY",
  "--verbose", "3"
)
"launching $exe $($args -join ' ')" | Add-Content $log
$p = Start-Process -FilePath $exe -ArgumentList $args -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $Root "pb_stdout.log") `
  -RedirectStandardError (Join-Path $Root "pb_stderr.log")
"pid=$($p.Id)" | Add-Content $log
Start-Sleep 3
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) {
  "running" | Add-Content $log
} else {
  "exited early (often needs Administrator — use run_pb_admin.ps1)" | Add-Content $log
  Get-Content (Join-Path $Root "pb_stderr.log") -ErrorAction SilentlyContinue | Add-Content $log
  Get-Content (Join-Path $Root "pb_stdout.log") -ErrorAction SilentlyContinue | Select-Object -Last 15 | Add-Content $log
}
