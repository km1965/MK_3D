$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$py = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creation de l'environnement virtuel Python 3.14..." -ForegroundColor Cyan
    py -3.14 -m venv .venv
    & $py -m pip install --upgrade pip
    & $py -m pip install -r requirements.txt
}

Write-Host "Installation de PyInstaller..." -ForegroundColor Cyan
& $py -m pip install --upgrade pyinstaller | Out-Null

Write-Host "Generation de l'icone..." -ForegroundColor Cyan
& $py tools\make_icon.py

Write-Host "Compilation de Mk_MNT_3D.exe (cela peut prendre quelques minutes)..." -ForegroundColor Cyan
& $py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "Mk_MNT_3D" `
    --icon "assets\mk_mnt_3d.ico" `
    --add-data "assets;assets" `
    --collect-all customtkinter `
    --collect-data matplotlib `
    app.py

Write-Host ""
Write-Host "Termine. Executable : dist\Mk_MNT_3D.exe" -ForegroundColor Green
