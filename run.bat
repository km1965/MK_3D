@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Environnement virtuel introuvable. Execution de l'installation...
    py -3.14 -m venv .venv || goto :error
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
)
.venv\Scripts\pythonw.exe app.py
exit /b 0
:error
echo.
echo Une erreur est survenue lors de l'installation.
pause
exit /b 1
