"""
WorkTracker 配置文件
"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据存储目录
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 数据库文件路径
DB_PATH = os.path.join(DATA_DIR, "work_tracker.db")

# 日报输出目录
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# 监控间隔（秒）
MONITOR_INTERVAL = 10

# 最小记录时长（秒），低于此值的活动会被忽略
MIN_DURATION = 5

# 空闲判断阈值（秒）- 无鼠标键盘操作超过此时间视为空闲
IDLE_THRESHOLD = 60

# 需要忽略的系统进程（不记录）
IGNORED_PROCESSES = [
    "SearchHost.exe",
    "ShellExperienceHost.exe",
    "RuntimeBroker.exe",
    "TextInputHost.exe",
    "dllhost.exe",
    "ctfmon.exe",
    "svchost.exe",
    "lsass.exe",
    "services.exe",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "fontdrvhost.exe",
    "WmiPrvSE.exe",
    "SecurityHealthService.exe",
    "sihost.exe",
    "taskhostw.exe",
    "dwm.exe",
    "conhost.exe",
    "SearchUI.exe",
    "StartMenuExperienceHost.exe",
    "TextInputHost.exe",
    "backgroundTaskHost.exe",
]

# 窗口标题忽略关键词
IGNORED_TITLES = [
    "任务切换",
    "音量合成器",
    "通知中心",
    "操作中心",
    "Windows 资源管理器",
]

# 进程名到工作类别映射（精确匹配）
CATEGORY_MAP = {
    # ===== 开发工具 =====
    "code.exe": "开发工具",
    "idea64.exe": "开发工具",
    "pycharm64.exe": "开发工具",
    "webstorm64.exe": "开发工具",
    "vscode.exe": "开发工具",
    "cursor.exe": "开发工具",
    "trae.exe": "开发工具",
    "trae solo cn.exe": "开发工具",
    "devenv.exe": "开发工具",
    "rider64.exe": "开发工具",
    "goland64.exe": "开发工具",
    "clion64.exe": "开发工具",
    "phpstorm64.exe": "开发工具",
    "webstorm64.exe": "开发工具",
    "datagrip64.exe": "数据库工具",
    
    # ===== 浏览器 =====
    "chrome.exe": "浏览器",
    "msedge.exe": "浏览器",
    "firefox.exe": "浏览器",
    "brave.exe": "浏览器",
    "opera.exe": "浏览器",
    "vivaldi.exe": "浏览器",
    "arc.exe": "浏览器",
    
    # ===== 通讯工具 =====
    "wechat.exe": "通讯工具",
    "wechatappex.exe": "通讯工具",
    "dingtalk.exe": "通讯工具",
    "lark.exe": "通讯工具",
    "feishu.exe": "通讯工具",
    "qq.exe": "通讯工具",
    "tim.exe": "通讯工具",
    "telegram.exe": "通讯工具",
    "skype.exe": "通讯工具",
    "teams.exe": "通讯工具",
    
    # ===== 邮件/办公 =====
    "outlook.exe": "邮件/办公",
    "foxmail.exe": "邮件/办公",
    "thunderbird.exe": "邮件/办公",
    
    # ===== 文档编辑 =====
    "winword.exe": "文档编辑",
    "wps.exe": "办公软件",
    "kingsoft.exe": "办公软件",
    
    # ===== 表格处理 =====
    "excel.exe": "表格处理",
    "et.exe": "表格处理",
    
    # ===== 演示文稿 =====
    "powerpnt.exe": "演示文稿",
    "wpp.exe": "演示文稿",
    
    # ===== 文本编辑 =====
    "notepad.exe": "文本编辑",
    "notepad++.exe": "文本编辑",
    "sublime_text.exe": "文本编辑",
    "ultraedit.exe": "文本编辑",
    "editplus.exe": "文本编辑",
    "vim.exe": "文本编辑",
    
    # ===== 远程工具 =====
    "xshell.exe": "远程工具",
    "xftp.exe": "远程工具",
    "mstsc.exe": "远程工具",
    "termius.exe": "远程工具",
    "securecrt.exe": "远程工具",
    "putty.exe": "远程工具",
    "mobaxterm.exe": "远程工具",
    "rustdesk.exe": "远程工具",
    "todesk.exe": "远程工具",
    "anydesk.exe": "远程工具",
    "sunloginclient.exe": "远程工具",
    
    # ===== 数据库工具 =====
    "navicat.exe": "数据库工具",
    "heidisql.exe": "数据库工具",
    "dbeaver.exe": "数据库工具",
    "sqlitestudio.exe": "数据库工具",
    
    # ===== API工具 =====
    "postman.exe": "API工具",
    "apifox.exe": "API工具",
    "apipost.exe": "API工具",
    
    # ===== 设计工具 =====
    "eagle.exe": "设计工具",
    "figma.exe": "设计工具",
    "photoshop.exe": "设计工具",
    "illustrator.exe": "设计工具",
    "axure.exe": "设计工具",
    "sketch.exe": "设计工具",
    
    # ===== 终端 =====
    "cmd.exe": "终端",
    "windowsterminal.exe": "终端",
    "pwsh.exe": "终端",
    "powershell.exe": "终端",
    "conemu64.exe": "终端",
    "tabby.exe": "终端",
    
    # ===== 播放器 =====
    "potplayer.exe": "播放器",
    "potplayermini64.exe": "播放器",
    "vlc.exe": "播放器",
    "wmplayer.exe": "播放器",
    "spotify.exe": "播放器",
    "cloudmusic.exe": "播放器",
    
    # ===== 下载工具 =====
    "thunder.exe": "下载工具",
    "idm.exe": "下载工具",
    "fdm.exe": "下载工具",
    
    # ===== AI工具 =====
    "chatgpt.exe": "AI工具",
    "copilot_desktop.exe": "AI工具",
    
    # ===== 文件管理 =====
    "explorer.exe": "文件管理",
    "totalcmd.exe": "文件管理",
    "everything.exe": "搜索工具",
    
    # ===== PDF阅读 =====
    "sumatrapdf.exe": "PDF阅读",
    "acrobat.exe": "PDF阅读",
    "foxitreader.exe": "PDF阅读",
    "pdf24.exe": "PDF阅读",
    
    # ===== 截图/录屏 =====
    "snipaste.exe": "截图工具",
    "screensnap.exe": "截图工具",
    "obs64.exe": "录屏工具",
    
    # ===== 代理/VPN =====
    "clash for windows.exe": "代理工具",
    "v2rayn.exe": "代理工具",
    
    # ===== 其他常见应用 =====
    "quark.exe": "浏览器",       # 夸克浏览器
    "xlsmartui.exe": "AI工具",   # 智能体
    "taptap.exe": "其他",        # TapTap游戏平台
}
