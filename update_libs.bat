@echo off
chcp 65001 >nul
title Update Libraries
echo === Script-U-Need: Update Libraries ===
echo.

call .venv\Scripts\activate.bat

echo Updating gu-funclib...
pip install --upgrade gu-funclib
if errorlevel 1 (
    echo ERROR: Failed to update gu-funclib.
    pause
    exit /b 1
)

echo.
echo === Installed version ===
pip show gu-funclib 2>nul | findstr /i "Name: Version:"

echo.
echo Update complete.
pause
