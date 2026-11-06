@echo off
cd /d "%~dp0"
if exist "%~dp0dist\车辆管理系统.exe" (
  start "" "%~dp0dist\车辆管理系统.exe"
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0车辆管理系统.py"
  exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0车辆管理系统.py"
  pause
  exit /b
)
echo 未找到 Python 环境，请先安装 Python 并勾选 Add to PATH
pause