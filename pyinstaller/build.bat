@echo off
REM ============================================================
REM  build.bat - Standard PyInstaller build (without Cython)
REM  Run from the pyinstaller/ directory.
REM ============================================================

setlocal
cd /d "%~dp0"
set PROJECT_ROOT=%~dp0..

echo ============================================================
echo  Podcast AI Studio - PyInstaller Build
echo ============================================================
echo.

REM Check Python
python --version 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found on PATH
    exit /b 1
)

REM Check PyInstaller
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller not installed. Run: pip install pyinstaller
    exit /b 1
)

REM Clean previous build artifacts
echo Cleaning previous build...
if exist "%PROJECT_ROOT%\dist\run_gui_app" rmdir /s /q "%PROJECT_ROOT%\dist\run_gui_app"
if exist "%PROJECT_ROOT%\build\run_gui_app" rmdir /s /q "%PROJECT_ROOT%\build\run_gui_app"
echo.

REM Run PyInstaller
echo Running PyInstaller...
echo.
python -m PyInstaller ^
    --distpath "%PROJECT_ROOT%\dist" ^
    --workpath "%PROJECT_ROOT%\build" ^
    --noconfirm ^
    --clean ^
    "%~dp0run_gui_app.spec"

if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo  BUILD FAILED
    echo ============================================================
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD SUCCESSFUL
echo  Output: %PROJECT_ROOT%\dist\run_gui_app\
echo  Run:    %PROJECT_ROOT%\dist\run_gui_app\run_gui_app.exe
echo ============================================================
endlocal
