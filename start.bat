@echo off
cls
title Script-U-Need

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo Starting...
python core\interface.py
pause
