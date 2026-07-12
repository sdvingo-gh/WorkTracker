"""
核心监控模块 - 负责实时捕获活动窗口、进程信息和系统状态
"""
import time
import atexit
import threading
import ctypes
from datetime import datetime

try:
    import win32gui
    import win32process
    import psutil
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False

from config import (
    MONITOR_INTERVAL, MIN_DURATION, IDLE_THRESHOLD,
    IGNORED_PROCESSES, IGNORED_TITLES, CATEGORY_MAP
)
from database import ActivityDB
from activity_parser import parse_window_title
from screen_analyzer import get_screen_analyzer


class ActivityMonitor:
    def __init__(self):
        self.db = ActivityDB()
        self.running = False
        self.paused = False
        self.monitor_thread = None
        self.start_time = None
        
        # 当前活动状态
        self.current_activity = None
        self.current_activity_id = None
        self.last_input_time = datetime.now()
        
        # 上一轮检测到的窗口信息（用于判断变化）
        self._last_hwnd = None
        self._last_title = ""
        
        # 回调函数列表
        self.on_activity_change_callbacks = []
        
        # 屏幕分析器（懒加载）
        self._screen_analyzer = None
    
    def _get_screen_analyzer(self):
        if self._screen_analyzer is None:
            try:
                self._screen_analyzer = get_screen_analyzer()
            except Exception:
                pass
        return self._screen_analyzer
    
    def _get_idle_duration(self) -> float:
        """获取系统空闲时长（秒）"""
        if not WINDOWS_AVAILABLE:
            return 0.0
        
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    
    def _get_active_window_info(self) -> dict:
        """获取当前活动窗口的详细信息，增加多重容错"""
        if not WINDOWS_AVAILABLE:
            return {"window_title": "未知", "process_name": "unknown", "pid": 0, "hwnd": 0}
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return {"window_title": "桌面", "process_name": "explorer.exe", "pid": 0, "hwnd": 0}
            
            window_title = win32gui.GetWindowText(hwnd) or ""
            
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            process_name = ""
            process_path = ""
            cpu_percent = 0.0
            memory_mb = 0.0
            
            if pid and pid > 0:
                try:
                    proc = psutil.Process(pid)
                    process_name = proc.name().lower()
                    try:
                        process_path = proc.exe() or ""
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                    cpu_percent = proc.cpu_percent(interval=0.05)
                    memory_mb = proc.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                    # psutil获取失败时，用win32备用方案获取进程名
                    try:
                        import win32api
                        import win32con
                        h_process = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
                        if h_process:
                            try:
                                import ctypes
                                buf = ctypes.create_unicode_buffer(1024)
                                ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, 1024)
                                process_path = buf.value
                                process_name = process_path.lower().split("\\")[-1]
                            except:
                                pass
                            finally:
                                win32api.CloseHandle(h_process)
                    except:
                        pass
            
            # 最后兜底：如果进程名仍为空，至少记录hwnd
            if not process_name:
                process_name = "unknown"
            
            return {
                "window_title": window_title,
                "process_name": process_name,
                "process_path": process_path,
                "pid": pid or 0,
                "hwnd": hwnd,
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_mb, 2)
            }
        except Exception as e:
            return {"window_title": "未知", "process_name": "unknown", "pid": 0, "hwnd": 0}
    
    def _get_category(self, process_name: str) -> str:
        """根据进程名判断工作类别"""
        proc_lower = process_name.lower()
        
        # 精确匹配
        if proc_lower in CATEGORY_MAP:
            return CATEGORY_MAP[proc_lower]
        
        # 模糊匹配：进程名包含关键字
        fuzzy_map = {
            "开发工具": ["code", "idea", "pycharm", "webstorm", "vscode", "cursor", "trae",
                       "devenv", "rider", "goland", "clion", "phpstorm"],
            "浏览器": ["chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "arc"],
            "通讯工具": ["wechat", "dingtalk", "lark", "feishu", "qq", "tim", "telegram",
                       "wechatappex", "skype", "teams"],
            "邮件/办公": ["outlook", "foxmail", "thunderbird"],
            "文档编辑": ["winword", "wps", "kingsoft"],
            "表格处理": ["excel", "et.exe", "numbers"],
            "演示文稿": ["powerpnt", "wpp", "keynote"],
            "文本编辑": ["notepad", "notepad++", "sublime", "ultraedit", "editplus", "vim"],
            "远程工具": ["xshell", "xftp", "mstsc", "termius", "securecrt", "putty", "mobaxterm",
                       "rustdesk", "todesk", "anydesk", "sunlogin"],
            "数据库工具": ["navicat", "datagrip", "heidisql", "dbeaver", "sqlitestudio",
                         "mysql", "pgadmin"],
            "API工具": ["postman", "apifox", "apipost", "insomnia", "hoppscotch"],
            "设计工具": ["photoshop", "illustrator", "figma", "eagle", "sketch", "axure",
                       "xd", "fireworks", "coreldraw"],
            "播放器": ["potplayer", "vlc", "wmplayer", "spotify", "cloudmusic"],
            "下载工具": ["thunder", "idm", "fdm", "aria2", "迅雷"],
        }
        
        for category, keywords in fuzzy_map.items():
            for kw in keywords:
                if kw in proc_lower:
                    return category
        
        return "其他"
    
    def _should_ignore(self, info: dict) -> bool:
        """判断是否应该忽略该活动"""
        proc = info.get("process_name", "").lower()
        title = info.get("window_title", "")
        
        # 忽略系统进程
        if proc in [p.lower() for p in IGNORED_PROCESSES]:
            return True
        
        # 忽略unknown进程
        if proc == "unknown":
            return True
        
        # 忽略特定标题
        for ignore in IGNORED_TITLES:
            if ignore in title:
                return True
        
        # 忽略无标题的空窗口（桌面除外）
        if (not title or title.strip() == "") and proc != "explorer.exe":
            return True
        
        return False
    
    def _is_idle(self) -> bool:
        """判断当前是否处于空闲状态"""
        return self._get_idle_duration() >= IDLE_THRESHOLD
    
    def _finish_current_activity(self, force: bool = False):
        """
        结束当前活动记录并更新数据库
        force=True 时忽略最小时长限制（停止监控时使用）
        """
        if self.current_activity is None or self.current_activity_id is None:
            return
        
        end_time = datetime.now()
        duration = int((end_time - self.current_activity["start_time"]).total_seconds())
        
        # force模式（停止时）或超过最小时长才写库
        if force or duration >= MIN_DURATION:
            self.db.update_activity_end(self.current_activity_id, end_time, max(duration, 1))
        
        # 触发回调
        self.current_activity["end_time"] = end_time
        self.current_activity["duration"] = duration
        for cb in self.on_activity_change_callbacks:
            try:
                cb("end", self.current_activity)
            except Exception:
                pass
        
        self.current_activity = None
        self.current_activity_id = None
    
    def _start_new_activity(self, info: dict, is_idle: bool = False):
        """开始新的活动记录"""
        self._finish_current_activity()
        
        now = datetime.now()
        
        # 解析窗口标题
        parsed = parse_window_title(
            info.get("window_title", ""),
            info.get("process_name", "")
        )
        
        activity = {
            "start_time": now,
            "end_time": None,
            "duration": 0,
            "window_title": info.get("window_title", ""),
            "process_name": info.get("process_name", ""),
            "process_path": info.get("process_path", ""),
            "pid": info.get("pid", 0),
            "hwnd": info.get("hwnd", 0),
            "cpu_percent": info.get("cpu_percent", 0.0),
            "memory_mb": info.get("memory_mb", 0.0),
            "category": "空闲" if is_idle else self._get_category(info.get("process_name", "")),
            "is_idle": is_idle,
            "file_name": parsed.get("file_name", ""),
            "project_name": parsed.get("project_name", ""),
            "page_title": parsed.get("page_title", ""),
            "context": parsed.get("context", ""),
            "app_type": parsed.get("app_type", "other"),
            "screen_text": "",
            "task_type": "其他",
            "task_confidence": 0.0,
            "app_context": "",
            "keywords": "",
            "screenshot_path": None
        }
        
        # 屏幕内容分析（非空闲时）
        if not is_idle and self._get_screen_analyzer():
            try:
                analyzer = self._get_screen_analyzer()
                analysis = analyzer.analyze_current_screen(
                    hwnd=info.get("hwnd", 0),
                    window_title=info.get("window_title", ""),
                    process_name=info.get("process_name", "")
                )
                activity["screen_text"] = analysis.get("screen_text", "")
                activity["task_type"] = analysis.get("task_type", "其他")
                activity["task_confidence"] = analysis.get("confidence", 0.0)
                activity["app_context"] = analysis.get("app_context", "")
                activity["keywords"] = ",".join(analysis.get("keywords", []))
                activity["screenshot_path"] = analysis.get("screenshot_path")
                
                # 如果屏幕分析更精确，用其分类覆盖
                if analysis.get("confidence", 0) > 0.3:
                    activity["category"] = analysis.get("task_type", activity["category"])
            except Exception:
                pass
        
        self.current_activity = activity
        self.current_activity_id = self.db.insert_activity(activity)
        
        # 触发回调
        for cb in self.on_activity_change_callbacks:
            try:
                cb("start", activity)
            except Exception:
                pass
    
    def _monitor_loop(self):
        """监控主循环"""
        was_idle = False
        _tick = 0
        
        while self.running:
            try:
                # 暂停时跳过
                if self.paused:
                    time.sleep(1)
                    continue
                
                idle = self._is_idle()
                
                if idle:
                    if not was_idle or self.current_activity is None:
                        self._start_new_activity(
                            {"window_title": "系统空闲", "process_name": "idle"},
                            is_idle=True
                        )
                        was_idle = True
                else:
                    info = self._get_active_window_info()
                    
                    # 判断窗口是否变化
                    window_changed = (
                        self._last_hwnd != info.get("hwnd") or
                        self._last_title != info.get("window_title")
                    )
                    
                    if window_changed:
                        if not self._should_ignore(info):
                            self._start_new_activity(info)
                            self._last_hwnd = info.get("hwnd")
                            self._last_title = info.get("window_title")
                            was_idle = False
                        else:
                            # 遇到忽略的窗口（如桌面），结束当前活动
                            self._finish_current_activity()
                            self._last_hwnd = info.get("hwnd")
                            self._last_title = info.get("window_title")
                    
                    was_idle = False
                
                # 每30秒实时更新当前活动的 duration 到数据库
                # 确保即使进程被杀（关机/崩溃），已记录的时间不会丢失
                _tick += 1
                if _tick % 3 == 0 and self.current_activity_id:
                    self._update_current_duration()
                
                time.sleep(MONITOR_INTERVAL)
                
            except Exception as e:
                # 防止单次异常导致监控崩溃
                time.sleep(MONITOR_INTERVAL)
    
    def _update_current_duration(self):
        """实时更新当前活动的 duration 到数据库（防崩溃丢数据）"""
        if self.current_activity is None or self.current_activity_id is None:
            return
        try:
            now = datetime.now()
            duration = int((now - self.current_activity["start_time"]).total_seconds())
            if duration > 0:
                # 只更新 duration，不动 end_time（保持"进行中"状态）
                conn = self.db._connect()
                conn.execute("UPDATE activities SET duration = ? WHERE id = ?", 
                           (duration, self.current_activity_id))
                conn.commit()
                conn.close()
        except Exception:
            pass
    
    def register_activity_callback(self, callback):
        self.on_activity_change_callbacks.append(callback)
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.start_time = datetime.now()
        self._last_hwnd = None
        self._last_title = ""
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        # 注册退出处理，确保关机/崩溃时也能保存数据
        atexit.register(self._emergency_save)
    
    def stop(self):
        self.running = False
        self.paused = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        # 停止时强制结束当前活动（忽略最小时长）
        self._finish_current_activity(force=True)
        self.start_time = None
    
    def _emergency_save(self):
        """紧急保存：进程退出时（关机/崩溃）强制保存当前活动"""
        try:
            self._finish_current_activity(force=True)
        except Exception:
            pass
    
    def pause(self):
        self.paused = True
        self._finish_current_activity(force=True)
    
    def resume(self):
        self.paused = False
        self._last_hwnd = None
        self._last_title = ""
    
    def get_current_activity(self) -> dict:
        if self.current_activity is None:
            return None
        result = self.current_activity.copy()
        result["current_duration"] = int((datetime.now() - result["start_time"]).total_seconds())
        return result
