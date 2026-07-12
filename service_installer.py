"""
WorkTracker Windows 服务模块
将 WorkTracker 注册为 Windows 系统服务，实现开机自启、后台静默运行

重要说明：
- Windows 服务运行在 Session 0（隔离会话），无法直接访问用户桌面
- 本服务采用"进程监控"模式：服务启动后会在当前用户会话中启动 WorkTracker 进程
- 这样既能享受服务管理的便利（开机自启、自动重启），又能正常监控桌面

使用方法：
  python service_installer.py install    # 安装服务
  python service_installer.py uninstall  # 卸载服务
  python service_installer.py start      # 启动服务
  python service_installer.py stop       # 停止服务
  python service_installer.py status     # 查看状态
  
  或使用 sc 命令：
  sc create WorkTracker binPath= "C:\...\dist\WorkTracker.exe" start= auto
  sc start WorkTracker
  sc stop WorkTracker
  sc delete WorkTracker
"""
import sys
import os
import time
import ctypes
import subprocess
import servicemanager
from datetime import datetime

# 服务相关依赖
try:
    import win32service
    import win32serviceutil
    import win32event
    import win32api
    import win32con
    import win32process
    import win32security
    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False
    print("pywin32 未安装，无法创建 Windows 服务。请运行: pip install pywin32")
    sys.exit(1)

from config import BASE_DIR, DATA_DIR


SERVICE_NAME = "WorkTracker"
SERVICE_DISPLAY_NAME = "WorkTracker 桌面活动监控"
SERVICE_DESCRIPTION = "自动监控桌面活动，记录工作时间，生成工作日报。双击桌面图标或访问 http://127.0.0.1:5678 查看数据。"


class WorkTrackerService(win32serviceutil.ServiceFramework):
    """WorkTracker Windows 服务"""
    
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.process = None
        self._log(f"服务初始化完成")
    
    def _log(self, msg):
        """写入服务日志"""
        try:
            servicemanager.LogInfoMsg(f"[WorkTracker] {msg}")
        except Exception:
            pass
        # 同时写入本地日志文件
        try:
            log_path = os.path.join(DATA_DIR, "service.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass
    
    def SvcDoRun(self):
        """服务启动时执行"""
        self._log("服务已启动")
        self.running = True
        
        # 在用户会话中启动 WorkTracker 进程
        self._start_worktracker()
        
        # 等待停止信号
        while self.running:
            # 检查进程是否还在运行
            if self.process:
                exit_code = self._check_process()
                if exit_code is not None and exit_code != 0:
                    self._log(f"WorkTracker 进程异常退出(code={exit_code})，5秒后重启...")
                    time.sleep(5)
                    if self.running:
                        self._start_worktracker()
            
            # 等待停止信号或超时
            rc = win32event.WaitForSingleObject(self.hWaitStop, 5000)
            if rc == win32event.WAIT_OBJECT_0:
                break
    
    def SvcStop(self):
        """服务停止时执行"""
        self._log("服务正在停止...")
        self.running = False
        self._stop_worktracker()
        win32event.SetEvent(self.hWaitStop)
    
    def _start_worktracker(self):
        """在用户会话中启动 WorkTracker Web GUI"""
        self._stop_worktracker()  # 先清理旧进程
        
        exe_path = os.path.join(BASE_DIR, "dist", "WorkTracker.exe")
        
        # 如果 EXE 不存在，使用 python 脚本启动
        if not os.path.exists(exe_path):
            python_exe = sys.executable
            script_path = os.path.join(BASE_DIR, "run.py")
            if not os.path.exists(script_path):
                script_path = os.path.join(BASE_DIR, "web_gui.py")
            cmd = f'"{python_exe}" "{script_path}"'
        else:
            cmd = f'"{exe_path}"'
        
        self._log(f"正在启动 WorkTracker: {cmd}")
        
        try:
            # 使用 CREATE_NO_WINDOW 避免弹出控制台窗口
            # 优先尝试在交互式用户会话中启动
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = 0  # SW_HIDE
            
            # 方法1：直接启动（如果服务以本地系统账户运行且允许与桌面交互）
            self.process = subprocess.Popen(
                cmd,
                shell=True,
                startupinfo=startup_info,
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=BASE_DIR
            )
            self._log(f"WorkTracker 已启动 (PID={self.process.pid})")
            
        except Exception as e:
            self._log(f"启动失败: {e}")
            # 尝试使用 win32 创建进程（在用户桌面会话中）
            try:
                self._start_in_user_session()
            except Exception as e2:
                self._log(f"用户会话启动也失败: {e2}")
    
    def _start_in_user_session(self):
        """使用 WTS API 在用户会话中启动进程（可访问桌面）"""
        try:
            # 查找当前用户的会话ID
            session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
            self._log(f"当前用户会话ID: {session_id}")
            
            # 获取用户令牌
            hToken = ctypes.c_void_p()
            rc = ctypes.windll.wtsapi32.WTSQueryUserToken(session_id, ctypes.byref(hToken))
            if rc == 0:
                raise Exception(f"WTSQueryUserToken 失败，错误码: {ctypes.windll.kernel32.GetLastError()}")
            
            # 获取环境变量
            pEnv = ctypes.c_void_p()
            ctypes.windll.user32.CreateEnvironmentBlock(ctypes.byref(pEnv), hToken, False)
            
            # 确定可执行文件路径
            exe_path = os.path.join(BASE_DIR, "dist", "WorkTracker.exe")
            if not os.path.exists(exe_path):
                exe_path = sys.executable  # python.exe
            
            exe_path = os.path.abspath(exe_path)
            
            # 创建进程
            process_info = ctypes.wintypes.PROCESS_INFORMATION()
            startup_info = ctypes.wintypes.STARTUPINFO()
            startup_info.cb = ctypes.sizeof(startup_info)
            startup_info.lpDesktop = "WinSta0\\Default"
            startup_info.dwFlags = 0
            startup_info.wShowWindow = 0  # SW_HIDE
            
            success = ctypes.windll.advapi32.CreateProcessAsUser(
                hToken,
                exe_path,
                None,
                None, None,
                False,
                win32con.CREATE_UNICODE_ENVIRONMENT | win32con.CREATE_NO_WINDOW,
                pEnv,
                BASE_DIR,
                ctypes.byref(startup_info),
                ctypes.byref(process_info)
            )
            
            # 清理
            ctypes.windll.user32.DestroyEnvironmentBlock(pEnv)
            ctypes.windll.kernel32.CloseHandle(hToken)
            
            if success:
                self._log(f"已在用户会话中启动 WorkTracker (PID={process_info.dwProcessId})")
                self._process_id = process_info.dwProcessId
                ctypes.windll.kernel32.CloseHandle(process_info.hProcess)
                ctypes.windll.kernel32.CloseHandle(process_info.hThread)
            else:
                raise Exception(f"CreateProcessAsUser 失败，错误码: {ctypes.windll.kernel32.GetLastError()}")
                
        except Exception as e:
            self._log(f"用户会话启动异常: {e}")
    
    def _stop_worktracker(self):
        """停止 WorkTracker 进程"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                self._log("WorkTracker 进程已停止")
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
    
    def _check_process(self):
        """检查进程是否已退出，返回 exit code 或 None"""
        if self.process:
            return self.process.poll()
        return None


def install_service():
    """安装服务"""
    if not SERVICE_AVAILABLE:
        print("错误: pywin32 未安装")
        return
    
    exe_path = os.path.abspath(sys.argv[0])
    if exe_path.endswith(".py"):
        # 脚本模式，需要用 python.exe
        exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    
    try:
        win32serviceutil.InstallService(
            exe_path,
            SERVICE_NAME,
            SERVICE_DISPLAY_NAME,
            startType=win32service.SERVICE_AUTO_START,  # 开机自启
            description=SERVICE_DESCRIPTION,
        )
        print(f"[成功] 服务 '{SERVICE_DISPLAY_NAME}' 已安装")
        print(f"  服务名称: {SERVICE_NAME}")
        print(f"  启动类型: 自动（开机自启）")
        print()
        print("下一步:")
        print(f"  1. 启动服务:  python {os.path.basename(__file__)} start")
        print(f"  2. 或使用:    net start {SERVICE_NAME}")
        print()
        print("启动后访问 http://127.0.0.1:5678 查看 Web 界面")
    except Exception as e:
        if "exists" in str(e).lower():
            print(f"服务 '{SERVICE_NAME}' 已存在，无需重复安装")
            print(f"如需重装，请先运行: python {os.path.basename(__file__)} uninstall")
        else:
            print(f"安装失败: {e}")


def uninstall_service():
    """卸载服务"""
    try:
        win32serviceutil.StopService(SERVICE_NAME)
        time.sleep(2)
    except Exception:
        pass
    
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
        print(f"[成功] 服务 '{SERVICE_NAME}' 已卸载")
    except Exception as e:
        if "does not exist" in str(e).lower():
            print(f"服务 '{SERVICE_NAME}' 不存在")
        else:
            print(f"卸载失败: {e}")


def start_service():
    """启动服务"""
    try:
        win32serviceutil.StartService(SERVICE_NAME)
        print(f"[成功] 服务 '{SERVICE_NAME}' 已启动")
        print("WorkTracker 正在后台运行，访问 http://127.0.0.1:5678 查看界面")
    except Exception as e:
        if "already running" in str(e).lower() or "already been started" in str(e).lower():
            print(f"服务 '{SERVICE_NAME}' 已经在运行中")
        else:
            print(f"启动失败: {e}")


def stop_service():
    """停止服务"""
    try:
        win32serviceutil.StopService(SERVICE_NAME)
        print(f"[成功] 服务 '{SERVICE_NAME}' 已停止")
    except Exception as e:
        if "is not started" in str(e).lower():
            print(f"服务 '{SERVICE_NAME}' 未在运行")
        else:
            print(f"停止失败: {e}")


def status_service():
    """查看服务状态"""
    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1]
        status_map = {
            1: "已停止",
            2: "正在启动...",
            3: "正在停止...",
            4: "正在运行",
        }
        status_text = status_map.get(status, f"未知({status})")
        
        print(f"服务名称:   {SERVICE_NAME}")
        print(f"显示名称:   {SERVICE_DISPLAY_NAME}")
        print(f"当前状态:   {status_text}")
        print(f"启动类型:   自动（开机自启）")
        print(f"Web 界面:   http://127.0.0.1:5678")
    except Exception:
        print(f"服务 '{SERVICE_NAME}' 未安装")


if __name__ == "__main__":
    import ctypes.wintypes
    
    commands = {
        "install": install_service,
        "uninstall": uninstall_service,
        "start": start_service,
        "stop": stop_service,
        "status": status_service,
    }
    
    # 如果以服务方式被调用（pywin32 框架）
    if len(sys.argv) == 1 and not any(arg in commands for arg in sys.argv):
        try:
            # 尝试作为服务运行
            win32serviceutil.HandleCommandLine(WorkTrackerService)
        except Exception as e:
            print(f"服务运行错误: {e}")
        sys.exit(0)
    
    # 命令行模式
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    if cmd in commands:
        commands[cmd]()
    else:
        print("用法:")
        print(f"  python {os.path.basename(__file__)} install    安装服务（开机自启）")
        print(f"  python {os.path.basename(__file__)} uninstall  卸载服务")
        print(f"  python {os.path.basename(__file__)} start      启动服务")
        print(f"  python {os.path.basename(__file__)} stop       停止服务")
        print(f"  python {os.path.basename(__file__)} status     查看状态")
