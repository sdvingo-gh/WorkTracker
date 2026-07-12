@echo off
chcp 65001 >nul 2>nul
:: WorkTracker 开机自启（非服务方式，通过任务计划程序实现）
:: 此方式更可靠：直接在用户桌面会话中运行，不存在 Session 0 隔离问题

echo.
echo ====================================================
echo   WorkTracker 开机自启设置
echo   (通过 Windows 任务计划程序实现)
echo ====================================================
echo.

set SCRIPT_PATH=%~dp0启动监控.bat
set TASK_NAME=WorkTracker_AutoStart

:: 创建定时任务（用户登录时自动运行）
schtasks /create /tn "%TASK_NAME%" /tr "\"%SCRIPT_PATH%\"" /sc onlogon /rl highest /f

if %errorlevel%==0 (
    echo [成功] 已设置开机自启！
    echo.
    echo 每次登录 Windows 后，WorkTracker 将自动启动。
    echo.
    echo 如需取消:
    echo   schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo [失败] 设置失败，请以管理员身份运行此脚本。
)

pause
