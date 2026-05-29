@echo off
chcp 65001 >nul
echo === Script-U-Need Setup ===
echo.

:: Check Python 3.10+
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10 or newer from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if %PYMAJ% LSS 3 (
    echo ERROR: Python 3.10+ required. Found: %PYVER%
    pause
    exit /b 1
)
if %PYMAJ% EQU 3 if %PYMIN% LSS 10 (
    echo ERROR: Python 3.10+ required. Found: %PYVER%
    pause
    exit /b 1
)
echo Python %PYVER% OK

:: Create virtual environment if needed
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists, skipping.
)

:: Activate
call .venv\Scripts\activate.bat

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo === Installed packages ===
pip show gradio pillow requests PyYAML 2>nul | findstr /i "Name: Version:"

echo.
echo Setup complete. Run start.bat to launch Script-U-Need.
pause
