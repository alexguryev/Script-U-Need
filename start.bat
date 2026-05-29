@echo off
cls
title Script-U-Need
call .venv\Scripts\activate.bat
echo Starting...
python core\interface.py
pause
