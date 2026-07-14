# 在仓库根目录启动 mitmdump（保证 ZJ_ORDER_ID 等环境变量真正传入）
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not $env:ZJ_ORDER_ID) {
  Write-Host "WARN: ZJ_ORDER_ID not set. Example: `$env:ZJ_ORDER_ID='你的14位订单号'" -ForegroundColor Yellow
}

$mitm = Get-Command mitmdump -ErrorAction SilentlyContinue
if (-not $mitm) {
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python314\Scripts\mitmdump.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts\mitmdump.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\mitmdump.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { $mitmPath = $c; break }
  }
} else {
  $mitmPath = $mitm.Source
}
if (-not $mitmPath) {
  Write-Host "mitmdump not found. pip install mitmproxy" -ForegroundColor Red
  exit 1
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "mitmdump" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 1

$order = $env:ZJ_ORDER_ID
$region = if ($env:ZJ_REGION) { $env:ZJ_REGION } else { "579" }
$aes = $env:ZJ_AES_KEY

# cmd /c set ... && 确保子进程继承环境变量
$sets = @("set `"ZJ_REGION=$region`"")
if ($order) { $sets = @("set `"ZJ_ORDER_ID=$order`"") + $sets }
if ($aes) { $sets += "set `"ZJ_AES_KEY=$aes`"" }
$sets += "`"$mitmPath`" -p 8888 -s minimal_fix.py --ssl-insecure --set block_global=false"
$cmdLine = ($sets -join " && ")

$p = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", $cmdLine) `
  -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $Root "mitm_stdout.log") `
  -RedirectStandardError (Join-Path $Root "mitm_stderr.log")

Start-Sleep 2
Write-Host "mitm launcher pid=$($p.Id) exited=$($p.HasExited)"
Write-Host "log: $(Join-Path $Root 'minimal_fix.log')"
if (Test-Path (Join-Path $Root "minimal_fix.log")) {
  Get-Content (Join-Path $Root "minimal_fix.log")
}

$pb = Get-Process ProxyBridge_CLI -ErrorAction SilentlyContinue
if (-not $pb) {
  Write-Host "ProxyBridge not running. Starting elevated (UAC)..." -ForegroundColor Yellow
  $pbScript = Join-Path $Root "run_pb_admin.ps1"
  if (Test-Path $pbScript) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
      "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $pbScript
    )
  } else {
    Write-Host "Run ProxyBridge as Administrator: Weixin.exe;WeChatAppEx.exe -> http://127.0.0.1:8888"
  }
} else {
  Write-Host "ProxyBridge already running pid=$($pb.Id)"
}

Write-Host ""
Write-Host "Next: fully quit WeChat, reopen, open order detail."
Write-Host "Success = minimal_fix.log contains: DETAIL body -> plain ..."
