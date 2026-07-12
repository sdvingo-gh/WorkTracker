"""
日报生成模块 - 负责将监控数据汇总生成美观的日报
"""
import os
import json
from datetime import datetime, date, timedelta
from collections import defaultdict

from config import REPORT_DIR
from database import ActivityDB


def format_duration(seconds: int) -> str:
    """将秒数格式化为 时:分"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


# 日报展示阈值（秒）
TIMELINE_SHOW_MIN = 300         # 时间线只显示超过5分钟的活动
SIGNIFICANT_DURATION = 1800     # 重点记录：超过30分钟
LONG_DURATION = 3600            # 长时间操作：超过1小时


def format_time(dt) -> str:
    """格式化时间为 HH:MM"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%H:%M")


def generate_daily_report(target_date: date = None, db: ActivityDB = None) -> str:
    """
    生成指定日期的工作日报，返回生成的HTML文件路径
    """
    if target_date is None:
        target_date = date.today()
    
    if db is None:
        db = ActivityDB()
    
    # 获取该天的活动记录
    activities = db.get_activities_by_date(target_date)
    
    if not activities:
        return None  # 当天没有记录
    
    # 获取统计信息
    stats = db.get_daily_stats(target_date)
    
    # 生成时间线数据
    timeline = []
    for act in activities:
        start = act.get("start_time")
        end = act.get("end_time")
        duration = act.get("duration", 0)
        
        if start and end:
            timeline.append({
                "start": format_time(start),
                "end": format_time(end),
                "duration": format_duration(duration),
                "seconds": duration,
                "title": act.get("window_title", "未知"),
                "process": act.get("process_name", ""),
                "category": act.get("category", "其他"),
                "is_idle": bool(act.get("is_idle", 0))
            })
    
    # 合并连续同类活动（优化时间线显示）
    merged_timeline = []
    for item in timeline:
        if not merged_timeline:
            merged_timeline.append(item.copy())
            continue
        
        last = merged_timeline[-1]
        # 如果进程相同且同类别且非空闲，合并
        if (last["process"] == item["process"] and 
            last["category"] == item["category"] and
            not last["is_idle"] and not item["is_idle"]):
            last["end"] = item["end"]
            last["seconds"] += item["seconds"]
            last["duration"] = format_duration(last["seconds"])
            last["title"] = item["title"]
        else:
            merged_timeline.append(item.copy())
    
    # 过滤：时间线只保留有意义的活动（超过5分钟 或 空闲记录 或 长时间操作）
    filtered_timeline = []
    short_others_seconds = 0
    for item in merged_timeline:
        if item["is_idle"] or item["seconds"] >= TIMELINE_SHOW_MIN:
            filtered_timeline.append(item)
        else:
            short_others_seconds += item["seconds"]
    
    # 如果有零散短操作，汇总为一条"零散操作"
    if short_others_seconds > 0:
        filtered_timeline.append({
            "start": "--",
            "end": "--",
            "duration": format_duration(short_others_seconds),
            "seconds": short_others_seconds,
            "title": f"其他零散操作（共 {format_duration(short_others_seconds)}）",
            "process": "多个应用",
            "category": "零散",
            "is_idle": False,
            "is_short_summary": True
        })
    
    merged_timeline = filtered_timeline
    
    # 计算时间段分布（每小时活跃度）
    hourly_activity = defaultdict(int)
    for act in activities:
        if act.get("is_idle"):
            continue
        start = act.get("start_time")
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        hour = start.hour
        hourly_activity[hour] += act.get("duration", 0)
    
    # 生成HTML
    html = build_report_html(target_date, stats, merged_timeline, hourly_activity)
    
    # 保存文件
    filename = f"work_report_{target_date.strftime('%Y%m%d')}.html"
    report_path = os.path.join(REPORT_DIR, filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    # 保存到数据库
    db.save_daily_summary(target_date, stats, report_path)
    
    return report_path


def build_report_html(report_date: date, stats: dict, timeline: list, hourly_activity: dict) -> str:
    """构建日报HTML内容"""
    
    date_str = report_date.strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][report_date.weekday()]
    
    active_duration = format_duration(stats.get("active_seconds", 0))
    idle_duration = format_duration(stats.get("idle_seconds", 0))
    
    # 计算活跃时段（有记录的第一个和最后一个时段）
    work_start = "--:--"
    work_end = "--:--"
    if timeline:
        non_idle = [t for t in timeline if not t["is_idle"]]
        if non_idle:
            work_start = non_idle[0]["start"]
            work_end = non_idle[-1]["end"]
    
    # 时间线HTML - 只展示有意义的活动
    timeline_html = ""
    for item in timeline:
        if item.get("is_short_summary"):
            # 零散操作汇总行
            timeline_html += f'''
            <div class="timeline-item short-summary">
                <div class="content">
                    <div class="title">{item['title']}</div>
                    <div class="meta">
                        <span class="category">零散</span>
                        <span class="duration">{item['duration']}</span>
                    </div>
                </div>
            </div>
            '''
        elif item["is_idle"]:
            timeline_html += f'''
            <div class="timeline-item idle">
                <div class="time">{item['start']} - {item['end']}</div>
                <div class="content">
                    <div class="title">空闲 / 离开</div>
                    <div class="duration">{item['duration']}</div>
                </div>
            </div>
            '''
        else:
            # 根据时长添加标签
            badge = ""
            if item["seconds"] >= LONG_DURATION:
                badge = '<span class="badge long">长时间</span>'
            elif item["seconds"] >= SIGNIFICANT_DURATION:
                badge = '<span class="badge sig">重点</span>'
            timeline_html += f'''
            <div class="timeline-item">
                <div class="time">{item['start']} - {item['end']}</div>
                <div class="content">
                    <div class="title">{item['title']} {badge}</div>
                    <div class="meta">
                        <span class="process">{item['process']}</span>
                        <span class="category">{item['category']}</span>
                        <span class="duration">{item['duration']}</span>
                    </div>
                </div>
            </div>
            '''
    
    # Top应用HTML - 只显示汇总时间超过1小时的应用
    top_apps_html = ""
    long_apps = [a for a in stats.get("top_apps", []) if a["seconds"] >= LONG_DURATION]
    if not long_apps:
        top_apps_html = '<div style="color:var(--text-secondary);padding:10px 0;">今日暂无超过1小时的长时间操作记录</div>'
    else:
        for i, app in enumerate(long_apps[:10], 1):
            bar_width = min(100, int((app["seconds"] / max(stats.get("active_seconds", 1), 1)) * 100))
            top_apps_html += f'''
            <div class="app-bar">
                <div class="app-info">
                    <span class="rank">{i}</span>
                    <span class="name">{app['process']}</span>
                    <span class="time">{format_duration(app['seconds'])}</span>
                </div>
                <div class="bar-bg"><div class="bar-fill" style="width:{bar_width}%"></div></div>
            </div>
            '''
    
    # 分类饼图数据（使用CSS conic-gradient模拟）
    categories = stats.get("categories", [])
    total_cat = sum(c["seconds"] for c in categories) or 1
    cat_html = ""
    colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]
    
    for i, cat in enumerate(categories[:6]):
        pct = int((cat["seconds"] / total_cat) * 100)
        color = colors[i % len(colors)]
        cat_html += f'''
        <div class="category-item">
            <div class="cat-color" style="background:{color}"></div>
            <div class="cat-name">{cat['category']}</div>
            <div class="cat-time">{format_duration(cat['seconds'])}</div>
            <div class="cat-pct">{pct}%</div>
        </div>
        '''
    
    # 每小时活跃度柱状图
    max_hour_val = max(hourly_activity.values()) if hourly_activity else 1
    bar_html = ""
    for h in range(24):
        val = hourly_activity.get(h, 0)
        height = int((val / max(max_hour_val, 1)) * 100)
        opacity = 0.3 + (0.7 * height / 100) if height > 0 else 0.15
        bar_html += f'''
        <div class="hour-col">
            <div class="hour-bar" style="height:{height}%;opacity:{opacity}"></div>
            <div class="hour-label">{h:02d}</div>
        </div>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>工作日报 - {date_str}</title>
    <style>
        :root {{
            --primary: #2563eb;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
            --idle: #cbd5e1;
        }}
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .subtitle {{ opacity: 0.9; font-size: 16px; }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--card);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .stat-card .number {{ font-size: 24px; font-weight: 700; color: var(--primary); margin: 8px 0; }}
        .stat-card .label {{ font-size: 13px; color: var(--text-secondary); }}
        
        .section {{
            background: var(--card);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .section h2 {{ font-size: 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
        
        /* 时间线 */
        .timeline {{ position: relative; padding-left: 20px; }}
        .timeline::before {{
            content: ''; position: absolute; left: 6px; top: 4px; bottom: 4px;
            width: 2px; background: var(--border);
        }}
        .timeline-item {{
            position: relative; margin-bottom: 16px;
            padding-left: 20px;
        }}
        .timeline-item::before {{
            content: ''; position: absolute; left: -18px; top: 6px;
            width: 10px; height: 10px; border-radius: 50%; background: var(--primary);
            border: 2px solid white;
        }}
        .timeline-item.idle::before {{ background: var(--idle); }}
        .timeline-item .time {{
            font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;
        }}
        .timeline-item .content {{ background: #f1f5f9; padding: 10px 14px; border-radius: 8px; }}
        .timeline-item .title {{ font-weight: 600; font-size: 14px; margin-bottom: 4px; }}
        .timeline-item .meta {{ font-size: 12px; color: var(--text-secondary); display: flex; gap: 12px; flex-wrap: wrap; }}
        .timeline-item .meta .duration {{ color: var(--primary); font-weight: 500; }}
        .timeline-item.idle .content {{ background: #f8fafc; }}
        .timeline-item.idle .title {{ color: var(--text-secondary); font-weight: 400; }}
        .timeline-item.short-summary .content {{ background: #f8fafc; border-left: 3px solid var(--border); }}
        .timeline-item.short-summary .title {{ color: var(--text-secondary); font-size: 13px; }}
        .badge {{ font-size: 10px; padding: 2px 8px; border-radius: 10px; margin-left: 6px; font-weight: 600; }}
        .badge.long {{ background: #dcfce7; color: #166534; }}
        .badge.sig {{ background: #dbeafe; color: #1e40af; }}
        
        /* 应用排行 */
        .app-bar {{ margin-bottom: 12px; }}
        .app-bar .app-info {{ display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }}
        .app-bar .rank {{ width: 20px; text-align: center; font-size: 12px; color: var(--text-secondary); }}
        .app-bar .name {{ flex: 1; font-size: 14px; font-weight: 500; }}
        .app-bar .time {{ font-size: 13px; color: var(--text-secondary); }}
        .app-bar .bar-bg {{ height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }}
        .app-bar .bar-fill {{ height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); border-radius: 3px; transition: width 0.5s; }}
        
        /* 分类 */
        .category-list {{ display: flex; flex-wrap: wrap; gap: 12px; }}
        .category-item {{ display: flex; align-items: center; gap: 8px; background: #f8fafc; padding: 8px 14px; border-radius: 20px; }}
        .cat-color {{ width: 10px; height: 10px; border-radius: 50%; }}
        .cat-name {{ font-size: 13px; }}
        .cat-time {{ font-size: 12px; color: var(--text-secondary); }}
        .cat-pct {{ font-size: 12px; font-weight: 600; color: var(--primary); margin-left: 4px; }}
        
        /* 小时活跃度 */
        .hour-chart {{ display: flex; align-items: flex-end; gap: 2px; height: 120px; padding-bottom: 20px; position: relative; }}
        .hour-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }}
        .hour-bar {{ width: 100%; background: var(--primary); border-radius: 2px 2px 0 0; min-height: 2px; transition: all 0.3s; }}
        .hour-label {{ font-size: 9px; color: var(--text-secondary); margin-top: 4px; }}
        
        .footer {{ text-align: center; color: var(--text-secondary); font-size: 12px; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>工作日报</h1>
            <div class="subtitle">{date_str} {weekday} | 自动生成</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">工作时长</div>
                <div class="number">{active_duration}</div>
            </div>
            <div class="stat-card">
                <div class="label">空闲/离开</div>
                <div class="number">{idle_duration}</div>
            </div>
            <div class="stat-card">
                <div class="label">起始时间</div>
                <div class="number" style="font-size:18px">{work_start}</div>
            </div>
            <div class="stat-card">
                <div class="label">结束时间</div>
                <div class="number" style="font-size:18px">{work_end}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>每小时活跃度分布</h2>
            <div class="hour-chart">
                {bar_html}
            </div>
        </div>
        
        <div class="section">
            <h2>工作类别分布</h2>
            <div class="category-list">
                {cat_html}
            </div>
        </div>
        
        <div class="section">
            <h2>长时间应用使用排行（超过1小时）</h2>
            {top_apps_html}
        </div>
        
        <div class="section">
            <h2>重点操作记录（单次超过5分钟）</h2>
            <div class="timeline">
                {timeline_html}
            </div>
        </div>
        
        <div class="footer">
            由 WorkTracker 自动生成 | 数据统计可能存在微小误差
        </div>
    </div>
</body>
</html>
'''
    return html


def generate_weekly_report(start_date: date = None, db: ActivityDB = None) -> str:
    """生成周报"""
    if start_date is None:
        start_date = date.today() - timedelta(days=date.today().weekday())
    
    if db is None:
        db = ActivityDB()
    
    end_date = start_date + timedelta(days=6)
    
    # 获取一周数据
    activities = db.get_date_range_activities(start_date, end_date)
    
    # 按天汇总
    daily_stats = {}
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily_stats[d.isoformat()] = db.get_daily_stats(d)
    
    # 简单输出周报文本
    lines = [
        f"# 工作周报 ({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})",
        "",
        "## 每日工作时长",
        ""
    ]
    
    total_active = 0
    for i in range(7):
        d = start_date + timedelta(days=i)
        stat = daily_stats.get(d.isoformat(), {})
        active = stat.get("active_seconds", 0)
        total_active += active
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][i]
        lines.append(f"- {d.strftime('%m-%d')} {weekday}: {format_duration(active)}")
    
    lines.append("")
    lines.append(f"**本周总计工作时长: {format_duration(total_active)}**")
    lines.append("")
    
    report_text = "\n".join(lines)
    
    filename = f"weekly_report_{start_date.strftime('%Y%m%d')}.md"
    report_path = os.path.join(REPORT_DIR, filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    return report_path
