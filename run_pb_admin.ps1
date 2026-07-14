$log = "C:\Users\54930\tools\wx_capture\proxybridge.log"
function L($m){ Add-Content $log ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }
"elevated $(Get-Date -Format o)" | Set-Content $log
Get-Process ProxyBridge_CLI,ProxyBridge -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 1
$p = Start-Process -FilePath "C:\Program Files\ProxyBridge\ProxyBridge_CLI.exe" -ArgumentList @(
  "--proxy","http://127.0.0.1:8888",
  "--rule","Weixin.exe;WeChatAppEx.exe:*:*:TCP:PROXY",
  "--verbose","3"
) -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput "C:\Users\54930\tools\wx_capture\pb_stdout.log" `
  -RedirectStandardError "C:\Users\54930\tools\wx_capture\pb_stderr.log"
L "pid=$($p.Id)"
Start-Sleep 3
if (Get-Process -Id $p.Id -EA SilentlyContinue) { L "ProxyBridge RUNNING" } else { L "ProxyBridge exited"; Get-Content "C:\Users\54930\tools\wx_capture\pb_stderr.log" -EA SilentlyContinue | ForEach-Object { L $_ } }
