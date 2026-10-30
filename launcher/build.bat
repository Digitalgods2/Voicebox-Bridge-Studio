@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

rem Builds VoiceBridgeStudio.exe into the project root. The launcher holds no ML
rem code; it starts the backend from backend\venv, so it stays a small build.
set "BUILD_VENV=build\launcher-venv"
if not exist "%BUILD_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BUILD_VENV%" || exit /b 1
)
"%BUILD_VENV%\Scripts\python.exe" -m pip install -q --upgrade pyinstaller pystray pillow || exit /b 1

"%BUILD_VENV%\Scripts\python.exe" -m PyInstaller ^
  --noconfirm --clean ^
  --onefile --windowed ^
  --name VoiceBridgeStudio ^
  --icon "%CD%\tauri\src-tauri\icons\icon.ico" ^
  --distpath build\launcher-dist ^
  --workpath build\launcher-work ^
  --specpath build ^
  --collect-all pystray ^
  launcher\launcher.py || exit /b 1

copy /Y "build\launcher-dist\VoiceBridgeStudio.exe" "VoiceBridgeStudio.exe" >nul || exit /b 1
echo.
echo Built VoiceBridgeStudio.exe in the project root. Keep it there: it finds
echo backend\venv, web\dist, and data\ relative to its own location.
