@echo off
REM ===================================================================
REM  Build script for the YouTube Content Dashboard
REM  Produces a standalone Windows executable that does NOT require
REM  Python to be installed on the target machine.
REM
REM  Final output:  dist\YouTubeContentDashboard.exe
REM ===================================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   YouTube Content Dashboard - Build
echo ============================================================
echo.

REM --- Locate Python -------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on your PATH.
    echo         Install Python 3.9+ from https://www.python.org/downloads/
    echo         and be sure to tick "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/4] Installing / updating application dependencies...
python -m pip install --upgrade customtkinter yt-dlp Pillow
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [3/4] Installing / updating PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

echo.
echo [4/4] Building the executable...

REM CustomTkinter ships data files (themes/assets) that must be bundled.
REM --collect-all pulls those in automatically.
pyinstaller --onefile --windowed --clean --noconfirm ^
    --name "YouTubeContentDashboard" ^
    --collect-all customtkinter ^
    --collect-all yt_dlp ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Scroll up for details.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD SUCCESSFUL
echo   Executable:  dist\YouTubeContentDashboard.exe
echo ============================================================
echo.
pause
endlocal
