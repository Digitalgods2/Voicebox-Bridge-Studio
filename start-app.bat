@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem VoiceBox Bridge Studio: one local backend serves TTS, voice cloning, speech-to-speech,
rem and the web UI, bound to loopback, using this folder's data\ workspace.
if not defined APP_PORT set "APP_PORT=17493"
set "APP_URL=http://127.0.0.1:%APP_PORT%"
set "APP_PYTHON=%CD%\backend\venv\Scripts\python.exe"

rem Exit codes: 0 = this app is already running, 11 = another service owns the port,
rem 20 = the port is available.
powershell.exe -NoProfile -Command "try { $status = Invoke-RestMethod -Uri '%APP_URL%/sts/status' -TimeoutSec 2; if (@($status.features) -contains 'workspace-voices-v1') { exit 0 } } catch {}; $client = [Net.Sockets.TcpClient]::new(); try { $client.Connect('127.0.0.1', %APP_PORT%); exit 11 } catch { exit 20 } finally { $client.Dispose() }" >nul 2>&1
set "PORT_STATE=%ERRORLEVEL%"
if "%PORT_STATE%"=="0" (
  echo VoiceBox Bridge Studio is already running.
  start "" "%APP_URL%"
  exit /b 0
)
if "%PORT_STATE%"=="11" (
  echo.
  echo Startup failed: port %APP_PORT% is in use by another application.
  echo If the separately installed VoiceBox app is open, close it - this app replaces it.
  echo Or set APP_PORT to a different port before running this script.
  pause
  exit /b 1
)

if not exist "%APP_PYTHON%" goto missing_python
"%APP_PYTHON%" -c "import torch, yt_dlp, backend.app" >nul 2>&1
if errorlevel 1 goto missing_python

if not exist "%CD%\web\dist\index.html" (
  where bun >nul 2>&1
  if errorlevel 1 (
    echo The web UI has not been built and Bun is not installed.
    echo Install Bun from https://bun.sh, then run this script again.
    pause
    exit /b 1
  )
  echo Building the web UI...
  call bun install
  call bun run build:web
  if errorlevel 1 (
    echo Startup failed: the web UI build did not complete.
    pause
    exit /b 1
  )
)

echo Starting VoiceBox Bridge Studio at %APP_URL% ...
start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "for ($attempt = 0; $attempt -lt 240; $attempt++) { try { $null = Invoke-RestMethod -Uri '%APP_URL%/health' -TimeoutSec 1; Start-Process '%APP_URL%'; exit 0 } catch {}; Start-Sleep -Milliseconds 500 }; exit 1"
"%APP_PYTHON%" -m backend.main --host 127.0.0.1 --port %APP_PORT% --data-dir "%CD%\data"
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
  echo.
  echo VoiceBox Bridge Studio exited with code %APP_EXIT%.
  pause
)
exit /b %APP_EXIT%

:missing_python
echo.
echo The backend environment is not finished installing.
echo If "just setup-python" is still running, wait for it to finish and try again.
echo Otherwise, from this folder, run:
echo   just setup-python
echo It installs PyTorch and the TTS engines - a multi-gigabyte download.
pause
exit /b 1
