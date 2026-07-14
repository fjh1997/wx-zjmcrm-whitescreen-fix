$ErrorActionPreference = "Continue"
$DIR = "C:\Users\54930\tools\wx_capture"
Set-Location $DIR

# Ensure pycryptodome for AES
& python -m pip install pycryptodome -q 2>$null

Write-Host "=== session_store ==="
if (Test-Path "$DIR\session_store.json") {
  Get-Content "$DIR\session_store.json"
} else {
  Write-Host "(no session yet)"
}

Write-Host "=== running auto_fuzz.py ==="
& python "$DIR\auto_fuzz.py" 2>&1 | Tee-Object -FilePath "$DIR\auto_fuzz_console.log"

Write-Host "=== best ==="
if (Test-Path "$DIR\auto_fuzz_best.json") {
  Get-Content "$DIR\auto_fuzz_best.json" -TotalCount 80
}
Write-Host "=== last 30 fuzz log ==="
if (Test-Path "$DIR\auto_fuzz.log") {
  Get-Content "$DIR\auto_fuzz.log" -Tail 30
}
