Get-Process ProxyBridge_CLI,ProxyBridge,mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1
$left = Get-Process ProxyBridge_CLI,ProxyBridge,mitmdump -ErrorAction SilentlyContinue
if (-not $left) {
  "STOPPED_OK" | Set-Content "C:\Users\54930\tools\wx_capture\stop_status.txt"
} else {
  ($left | ForEach-Object { $_.ProcessName + " " + $_.Id }) -join "," | Set-Content "C:\Users\54930\tools\wx_capture\stop_status.txt"
}
