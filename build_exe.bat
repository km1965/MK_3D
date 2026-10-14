@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"
if errorlevel 1 (
    echo.
    echo Echec de la compilation.
    pause
    exit /b 1
)
echo.
echo Executable pret dans dist\Mk_MNT_3D.exe
pause
