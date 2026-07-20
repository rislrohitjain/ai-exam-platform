@echo off
setlocal

title AI Exam Platform - Local Server

:: Change to project root directory (same folder as this .bat file)
cd /d "%~dp0"

:: Detect local IP using Python
for /f "delims=" %%i in ('python -c "import socket; s=socket.socket(); s.connect((chr(56)+chr(46)+chr(56)+chr(46)+chr(56)+chr(46)+chr(56),80)); print(s.getsockname()[0]); s.close()" 2^>nul') do set LOCAL_IP=%%i
if not defined LOCAL_IP (
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
        if not defined LOCAL_IP (
            set LOCAL_IP=%%a
            :: strip leading space
            call set LOCAL_IP=%%LOCAL_IP: =%%
        )
    )
)
if not defined LOCAL_IP set LOCAL_IP=127.0.0.1

echo.
echo ================================================================================
echo   Advanced AI Exam ^& Evaluation Platform
echo ================================================================================
echo.
echo   [INFO] Detected Local IP : %LOCAL_IP%
echo   [INFO] Port              : 8000
echo.
echo   Access URLs:
echo     Localhost   : http://127.0.0.1:8000/static/index.html
echo     Local Net   : http://%LOCAL_IP%:8000/static/index.html
echo     API Docs    : http://%LOCAL_IP%:8000/docs
echo.
echo ================================================================================
echo.

:: Activate virtual environment if present
if exist "venv\Scripts\activate.bat" (
    echo   [INFO] Activating virtual environment ^(venv^)...
    call "venv\Scripts\activate.bat"
    goto :check_uvicorn
)
if exist ".venv\Scripts\activate.bat" (
    echo   [INFO] Activating virtual environment ^(.venv^)...
    call ".venv\Scripts\activate.bat"
    goto :check_uvicorn
)
echo   [WARN] No virtual environment found. Using system Python.
echo   [WARN] If packages are missing, run: pip install -r requirements.txt
echo.

:check_uvicorn
:: Check if uvicorn is available
python -m uvicorn --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] uvicorn not found. Installing requirements...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo   [ERROR] Failed to install requirements. Exiting.
        pause
        exit /b 1
    )
)

echo   [INFO] Starting server... Press Ctrl+C to stop.
echo.

:: Run the FastAPI server bound to all interfaces
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo   [INFO] Server stopped.
pause
