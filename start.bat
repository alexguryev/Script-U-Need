@echo off
cls
title Script-U-Need

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

:: gu-funclib is an external PyPI dependency - install it on the first run
python -c "import gu_funclib" >nul 2>&1
if errorlevel 1 (
    echo Installing gu-funclib from PyPI...
    python -m pip install --upgrade gu-funclib
    if errorlevel 1 (
        echo ERROR: Failed to install gu-funclib. Check your internet connection or run setup.bat.
        pause
        exit /b 1
    )
)

echo Starting...
python core\interface.py
pause
