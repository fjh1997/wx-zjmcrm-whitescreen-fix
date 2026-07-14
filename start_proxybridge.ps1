$ErrorActionPreference = "Continue"
$log = "C:\Users\54930\tools\wx_capture\proxybridge.log"
"start $(Get-Date -Format o)" | Set-Content $log

# stop old ProxyBridge CLI
Get-Process ProxyBridge_CLI,ProxyBridge -EA SilentlyContinue | ForEach-Object {
  try { Stop-Process -Id $_.Id -Force; "killed $($_.ProcessName) $($_.Id)" | Add-Content $log } catch {}
}
Start-Sleep 1

$exe = "C:\Program Files\ProxyBridge\ProxyBridge_CLI.exe"
$args = @(
  "--proxy","http://127.0.0.1:8888",
  "--rule","Weixin.exe;WeChatAppEx.exe:*:80;443:TCP:PROXY",
  "--rule","Weixin.exe;WeChatAppEx.exe:127.*;*:TCP:DIRECT",
  "--rule","Weixin.exe;WeChatAppEx.exe:192.168.*;*:TCP:DIRECT",
  "--verbose","3"
)
# note: dns-via-proxy default true; for HTTP mitm proxy localhost DNS is ok

"launching $exe $($args -join ' ')" | Add-Content $log
$p = Start-Process -FilePath $exe -ArgumentList $args -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput "C:\Users\54930\tools\wx_capture\pb_stdout.log" `
  -RedirectStandardError "C:\Users\54930\tools\wx_capture\pb_stderr.log"
"pid=$($p.Id)" | Add-Content $log
Start-Sleep 3
if (Get-Process -Id $p.Id -EA SilentlyContinue) { "running" | Add-Content $log } else { "exited early" | Add-Content $log; Get-Content "C:\Users\54930\tools\wx_capture\pb_stderr.log" -EA SilentlyContinue | Add-Content $log }
