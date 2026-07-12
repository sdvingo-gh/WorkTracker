#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkTracker 启动入口（EXE打包用）
双击运行后：启动监控 + 打开Web浏览器界面
"""
import os
import sys
import webbrowser
import threading
import time

# 确保工作目录正确
if getattr(sys, 'frozen', False):
    # PyInstaller打包后，资源在exe同目录
    os.chdir(os.path.dirname(sys.executable))
    sys.path.insert(0, os.path.dirname(sys.executable))
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def start_web_gui():
    """启动Web GUI服务"""
    from web_gui import app
    import webbrowser
    
    def open_browser():
        time.sleep(2)
        webbrowser.open('http://127.0.0.1:5678')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 在主线程运行Flask（必须用 reloader=False）
    app.run(host='127.0.0.1', port=5678, debug=False, use_reloader=False)


def main():
    # 初始化数据库
    from database import init_db
    init_db()
    
    # 启动监控
    from monitor import ActivityMonitor
    monitor = ActivityMonitor()
    monitor.start()
    print("[WorkTracker] 监控已启动")
    
    # 启动Web GUI
    print("[WorkTracker] 正在启动Web界面...")
    start_web_gui()


if __name__ == '__main__':
    main()
