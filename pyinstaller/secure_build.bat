@echo off
REM ============================================================
REM  secure_build.bat - Full build with Cython source protection
REM  Step 1: Compile modules with Cython (.py -> .pyd)
REM  Step 2: Run PyInstaller build with compiled modules
REM  Step 3: Generate distributable folder
REM  Run from the pyinstaller/ directory.
REM ============================================================

setlocal
cd /d "%~dp0"
set PROJECT_ROOT=%~dp0..

echo ============================================================
echo  Podcast AI Studio - Secure Build (Cython + PyInstaller)
echo ============================================================
echo.

REM Check Python
python --version 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found on PATH
    exit /b 1
)

REM Check required packages
python -c "import Cython" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Cython not installed. Run: pip install cython
    exit /b 1
)
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller not installed. Run: pip install pyinstaller
    exit /b 1
)

REM ============================================================
REM  Step 1: Compile modules with Cython
REM ============================================================
echo.
echo [Step 1/3] Compiling Python modules with Cython...
echo.
python "%~dp0cython_build.py"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Cython compilation failed
    exit /b 1
)

REM Verify compiled modules exist
if not exist "%~dp0compiled_modules" (
    echo ERROR: compiled_modules directory not created
    exit /b 1
)

echo.
echo [Step 1/3] Cython compilation complete.
echo.

REM ============================================================
REM  Step 2: Clean previous build artifacts
REM ============================================================
echo [Step 2/3] Cleaning and running PyInstaller...
echo.
if exist "%PROJECT_ROOT%\dist\run_gui_app" rmdir /s /q "%PROJECT_ROOT%\dist\run_gui_app"
if exist "%PROJECT_ROOT%\build\run_gui_app" rmdir /s /q "%PROJECT_ROOT%\build\run_gui_app"

REM ============================================================
REM  Step 3: Run PyInstaller with compiled modules
REM ============================================================
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
echo  SECURE BUILD SUCCESSFUL
echo  Output: %PROJECT_ROOT%\dist\run_gui_app\
echo  Run:    %PROJECT_ROOT%\dist\run_gui_app\run_gui_app.exe
echo ============================================================
echo.
echo  Protected modules (compiled to .pyd):
dir /b "%~dp0compiled_modules\*.pyd" 2>nul
echo.
echo  Original .py source files are NOT included in the
echo  distribution for the above modules.
echo ============================================================
endlocal
