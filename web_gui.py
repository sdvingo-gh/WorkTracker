"""
WorkTracker Web GUI - Flask 后端服务
提供REST API与前端HTML页面
"""
import os
import sys
import json
import webbrowser
import threading
from datetime import date, datetime

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, ActivityDB
from monitor import ActivityMonitor
from reporter import generate_daily_report, generate_weekly_report, format_duration
from config import REPORT_DIR, DATA_DIR, BASE_DIR
from activity_parser import parse_window_title
from daily_editor import build_daily_report_data

app = Flask(__name__)

# 全局监控实例
monitor = ActivityMonitor()
db = ActivityDB()
oa_filler_instance = None  # OA填写实例

# ===================== 页面路由 =====================

@app.route("/")
def index():
    resp = send_from_directory('static', 'index.html')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route("/reports/<path:filename>")
def serve_report(filename):
    """提供生成的日报文件访问"""
    return send_from_directory(REPORT_DIR, filename)


# ===================== 监控控制 API =====================

@app.route("/api/status")
def api_status():
    """获取监控状态"""
    current = monitor.get_current_activity()
    return jsonify({
        "running": monitor.running,
        "paused": getattr(monitor, "paused", False),
        "current_activity": current,
        "uptime": getattr(monitor, "start_time", None)
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    """启动监控"""
    if not monitor.running:
        init_db()
        monitor.start()
        return jsonify({"success": True, "message": "监控已启动"})
    return jsonify({"success": False, "message": "监控已在运行中"})


@app.route("/api/pause", methods=["POST"])
def api_pause():
    """暂停/恢复监控"""
    if not monitor.running:
        return jsonify({"success": False, "message": "监控未运行"})
    
    was_paused = getattr(monitor, "paused", False)
    monitor.paused = not was_paused
    state = "已暂停" if monitor.paused else "已恢复"
    return jsonify({"success": True, "message": f"监控{state}", "paused": monitor.paused})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """停止监控"""
    if monitor.running:
        monitor.stop()
        monitor.paused = False
        return jsonify({"success": True, "message": "监控已停止"})
    return jsonify({"success": False, "message": "监控未运行"})


# ===================== 统计数据 API =====================

@app.route("/api/today-stats")
def api_today_stats():
    """获取今日统计"""
    stats = db.get_daily_stats(date.today())
    return jsonify(stats)


def _enrich_activity(a: dict) -> dict:
    """为活动记录补充解析后的结构化信息"""
    parsed = parse_window_title(
        a.get("window_title", ""),
        a.get("process_name", "")
    )
    return {
        "id": a["id"],
        "start_time": a["start_time"],
        "end_time": a["end_time"],
        "duration": a["duration"],
        "window_title": a["window_title"],
        "process_name": a["process_name"],
        "category": a.get("task_type", "") or a["category"],  # 屏幕分析优先
        "is_idle": bool(a["is_idle"]),
        "file_name": a.get("file_name", "") or parsed.get("file_name", ""),
        "project_name": a.get("project_name", "") or parsed.get("project_name", ""),
        "page_title": a.get("page_title", "") or parsed.get("page_title", ""),
        "context": a.get("context", "") or parsed.get("context", ""),
        "app_type": a.get("app_type", "") or parsed.get("app_type", "other"),
        "app_context": a.get("app_context", ""),
        "keywords": a.get("keywords", ""),
        "task_confidence": a.get("task_confidence", 0),
        "screenshot_path": a.get("screenshot_path", ""),
    }


@app.route("/api/today-activities")
def api_today_activities():
    """获取今日活动明细（含解析后的结构化信息）"""
    activities = db.get_activities_by_date(date.today())
    return jsonify([_enrich_activity(a) for a in activities])


@app.route("/api/dates")
def api_dates():
    """获取所有有记录的日期"""
    dates = db.get_all_dates()
    return jsonify(dates)


@app.route("/api/activities/<date_str>")
def api_activities_by_date(date_str):
    """获取指定日期的活动"""
    try:
        d = date.fromisoformat(date_str)
    except:
        return jsonify({"error": "无效日期"}), 400
    activities = db.get_activities_by_date(d)
    return jsonify([_enrich_activity(a) for a in activities])


@app.route("/api/stats/<date_str>")
def api_stats_by_date(date_str):
    """获取指定日期的统计"""
    try:
        d = date.fromisoformat(date_str)
    except:
        return jsonify({"error": "无效日期"}), 400
    return jsonify(db.get_daily_stats(d))


# ===================== 日报生成 API =====================

@app.route("/api/report/today", methods=["POST"])
def api_report_today():
    """生成今日日报"""
    path = generate_daily_report(date.today(), db)
    if path:
        filename = os.path.basename(path)
        return jsonify({"success": True, "url": f"/reports/{filename}"})
    return jsonify({"success": False, "message": "无数据"})


@app.route("/api/report/<date_str>", methods=["POST"])
def api_report_date(date_str):
    """生成指定日期日报"""
    try:
        d = date.fromisoformat(date_str)
    except:
        return jsonify({"error": "无效日期"}), 400
    path = generate_daily_report(d, db)
    if path:
        filename = os.path.basename(path)
        return jsonify({"success": True, "url": f"/reports/{filename}"})
    return jsonify({"success": False, "message": f"{date_str} 无数据"})


@app.route("/api/report/weekly", methods=["POST"])
def api_report_weekly():
    """生成周报"""
    path = generate_weekly_report(date.today(), db)
    if path:
        filename = os.path.basename(path)
        return jsonify({"success": True, "url": f"/reports/{filename}"})
    return jsonify({"success": False, "message": "无数据"})


# ===================== 参数设置 API =====================

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """获取当前配置"""
    from config import (MONITOR_INTERVAL, MIN_DURATION, IDLE_THRESHOLD,
                        IGNORED_PROCESSES, IGNORED_TITLES)
    return jsonify({
        "monitor_interval": MONITOR_INTERVAL,
        "min_duration": MIN_DURATION,
        "idle_threshold": IDLE_THRESHOLD,
        "ignored_processes": IGNORED_PROCESSES,
        "ignored_titles": IGNORED_TITLES
    })


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """保存配置（运行时动态修改，重启后恢复默认）"""
    data = request.json
    if not data:
        return jsonify({"error": "无数据"}), 400
    
    import config
    if "monitor_interval" in data:
        config.MONITOR_INTERVAL = max(5, int(data["monitor_interval"]))
    if "min_duration" in data:
        config.MIN_DURATION = max(5, int(data["min_duration"]))
    if "idle_threshold" in data:
        config.IDLE_THRESHOLD = max(60, int(data["idle_threshold"]))
    
    return jsonify({
        "success": True,
        "message": "设置已保存（仅本次运行有效）",
        "settings": {
            "monitor_interval": config.MONITOR_INTERVAL,
            "min_duration": config.MIN_DURATION,
            "idle_threshold": config.IDLE_THRESHOLD
        }
    })


# ===================== 数据管理 API =====================

@app.route("/api/clear-today", methods=["POST"])
def api_clear_today():
    """清除今日数据"""
    conn = db._connect()
    conn.execute("DELETE FROM activities WHERE date(start_time) = ?", (date.today().isoformat(),))
    conn.execute("DELETE FROM daily_summaries WHERE summary_date = ?", (date.today().isoformat(),))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "今日数据已清除"})


# ===================== OA 提交 API =====================

@app.route("/api/oa/preview")
def api_oa_preview():
    """预览日报数据（用于OA填写前的编辑确认）"""
    date_str = request.args.get("date", date.today().isoformat())
    try:
        d = date.fromisoformat(date_str)
    except:
        return jsonify({"error": "无效日期"}), 400
    report = build_daily_report_data(d, db)
    return jsonify(report)


@app.route("/api/oa/config", methods=["GET"])
def api_oa_get_config():
    """获取OA配置"""
    from daily_editor import load_oa_config
    return jsonify(load_oa_config())


@app.route("/api/oa/config", methods=["POST"])
def api_oa_save_config():
    """保存OA配置"""
    from daily_editor import save_oa_config
    data = request.json
    if not data:
        return jsonify({"error": "无数据"}), 400
    save_oa_config(data)
    return jsonify({"success": True, "message": "OA配置已保存"})


@app.route("/api/oa/submit", methods=["POST"])
def api_oa_submit():
    """启动OA自动填写（后台线程）"""
    from daily_editor import build_daily_report_data
    from oa_filler import fill_report_async
    
    data = request.json
    if not data:
        return jsonify({"error": "无数据"}), 400
    
    date_str = data.get("date", date.today().isoformat())
    config = data.get("config", {})
    edited_report = data.get("report", None)
    
    try:
        d = date.fromisoformat(date_str)
    except:
        return jsonify({"error": "无效日期"}), 400
    
    # 使用用户编辑后的日报数据，或自动生成
    report_data = edited_report or build_daily_report_data(d, db)
    
    # 检查OA URL
    if not config.get("oa_url"):
        return jsonify({"success": False, "message": "请先在OA设置中配置日报页面URL"})
    
    # 后台线程启动填写
    global oa_filler_instance
    oa_filler_instance = fill_report_async(date_str, report_data, config)
    
    return jsonify({"success": True, "message": "已启动OA填写，请查看浏览器窗口"})


@app.route("/api/oa/status")
def api_oa_status():
    """获取OA填写状态"""
    if oa_filler_instance:
        return jsonify(oa_filler_instance.get_status())
    return jsonify({"status": "idle", "message": "未启动"})


# ===================== 前端页面 HTML =====================




def main():
    """启动Web GUI服务"""
    init_db()
    port = 5678
    
    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}")
    
    timer = threading.Timer(1.5, open_browser)
    timer.daemon = True
    timer.start()
    
    print("=" * 50)
    print("  WorkTracker Web GUI 已启动")
    print(f"  访问地址: http://127.0.0.1:{port}")
    print("  按 Ctrl+C 停止服务")
    print("=" * 50)
    
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
