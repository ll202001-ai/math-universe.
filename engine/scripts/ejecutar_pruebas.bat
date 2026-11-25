@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
python -m pytest tests -v -p no:cacheprovider
exit /b %ERRORLEVEL%
