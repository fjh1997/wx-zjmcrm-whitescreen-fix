$ErrorActionPreference = "Continue"
Get-Process mitmdump -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue
Start-Sleep 1
$p = Start-Process -FilePath "C:\Users\54930\AppData\Local\Programs\Python\Python314\Scripts\mitmdump.exe" -ArgumentList @(
  "-p","8888",
  "-s","C:\Users\54930\tools\wx_capture\minimal_fix.py",
  "--set","block_global=false",
  "--ssl-insecure"
) -WorkingDirectory "C:\Users\54930\tools\wx_capture" `
  -RedirectStandardOutput "C:\Users\54930\tools\wx_capture\mitm_stdout.log" `
  -RedirectStandardError "C:\Users\54930\tools\wx_capture\mitm_stderr.log" `
  -WindowStyle Hidden -PassThru
Start-Sleep 2
"mitm=$($p.Id) exited=$($p.HasExited)"
Get-Process mitmdump,ProxyBridge_CLI -EA SilentlyContinue | Format-Table Id,ProcessName -AutoSize
Get-Content C:\Users\54930\tools\wx_capture\minimal_fix.log -EA SilentlyContinue
if (Test-Path C:\Users\54930\tools\wx_capture\mitm_stderr.log) {
  "--- stderr ---"
  Get-Content C:\Users\54930\tools\wx_capture\mitm_stderr.log -Tail 10
}
$pb = Get-Process ProxyBridge_CLI -EA SilentlyContinue
if (-not $pb) {
  "ProxyBridge missing, try elevate..."
  Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File C:\Users\54930\tools\wx_capture\run_pb_admin.ps1" -Verb RunAs
  Start-Sleep 3
  Get-Process ProxyBridge_CLI -EA SilentlyContinue | Format-Table Id,ProcessName
}
