@echo off
chcp 65001 >nul 2>nul
echo.
echo ====================================================
echo   WorkTracker 服务管理
echo ====================================================
echo.

if "%1"=="install" goto install
if "%1"=="uninstall" goto uninstall
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="status" goto status
goto menu

:menu
echo   [1] 安装服务（开机自启）
echo   [2] 卸载服务
echo   [3] 启动服务
echo   [4] 停止服务
echo   [5] 查看状态
echo   [0] 退出
echo.
set /p choice=请选择操作: 
if "%choice%"=="1" goto install
if "%choice%"=="2" goto uninstall
if "%choice%"=="3" goto start
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto status
if "%choice%"=="0" exit
echo 无效选择
pause
exit

:install
echo 正在安装 WorkTracker 服务...
python "%~dp0service_installer.py" install
if %errorlevel%==0 (
    echo.
    echo 是否立即启动服务? (Y/N)
    set /p auto_start=请选择: 
    if /i "%auto_start%"=="Y" goto start
)
pause
exit

:uninstall
echo 正在停止并卸载服务...
python "%~dp0service_installer.py" stop
timeout /t 2 /nobreak >nul
python "%~dp0service_installer.py" uninstall
pause
exit

:start
echo 正在启动服务...
python "%~dp0service_installer.py" start
echo.
echo 提示: 启动后访问 http://127.0.0.1:5678 查看 Web 界面
pause
exit

:stop
echo 正在停止服务...
python "%~dp0service_installer.py" stop
pause
exit

:status
python "%~dp0service_installer.py" status
pause
exit
