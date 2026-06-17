$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
  $candidate = Join-Path $env:APPDATA "Python\Python312\Scripts\pyinstaller.exe"
  if (Test-Path $candidate) {
    $pyinstaller = Get-Item $candidate
  }
}
if (-not $pyinstaller) {
  throw "PyInstaller not found. Run: python -m pip install -r requirements.txt"
}

$pyinstallerPath = if ($pyinstaller.Source) { $pyinstaller.Source } else { $pyinstaller.FullName }

& $pyinstallerPath `
  --onefile `
  --name furuyoni_auto_post `
  --clean `
  src\furuyoni_auto_post.py

Write-Host "Built: $root\dist\furuyoni_auto_post.exe"
