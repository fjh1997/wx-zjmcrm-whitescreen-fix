# 需管理员。将 Weixin / WeChatAppEx 流量指到本机 mitm 8888
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $Root "proxybridge.log"

function L($m) { Add-Content $log ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }

"elevated $(Get-Date -Format o)" | Set-Content $log
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
L "admin=$isAdmin"
if (-not $isAdmin) {
  L "ERROR: need Administrator"
  Write-Host "ProxyBridge requires Administrator. Re-run elevated." -ForegroundColor Red
  exit 1
}

Get-Process ProxyBridge_CLI, ProxyBridge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1

$exe = "C:\Program Files\ProxyBridge\ProxyBridge_CLI.exe"
if (-not (Test-Path $exe)) {
  L "ERROR: not found $exe"
  Write-Host "Install ProxyBridge CLI first." -ForegroundColor Red
  exit 1
}

$args = @(
  "--proxy", "http://127.0.0.1:8888",
  "--rule", "Weixin.exe;WeChatAppEx.exe:*:*:TCP:PROXY",
  "--verbose", "3"
)
L "launching $exe $($args -join ' ')"
$p = Start-Process -FilePath $exe -ArgumentList $args -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $Root "pb_stdout.log") `
  -RedirectStandardError (Join-Path $Root "pb_stderr.log")
L "pid=$($p.Id)"
Start-Sleep 2
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) {
  L "ProxyBridge RUNNING"
  Write-Host "ProxyBridge RUNNING pid=$($p.Id)"
} else {
  L "ProxyBridge exited"
  Get-Content (Join-Path $Root "pb_stdout.log") -ErrorAction SilentlyContinue | Select-Object -Last 20 | ForEach-Object { L $_ }
  exit 1
}
