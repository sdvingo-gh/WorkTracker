"""
数据库模块 - 负责活动记录的存储和查询
"""
import sqlite3
import json
from datetime import datetime, date
from config import DB_PATH


def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 活动记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration INTEGER DEFAULT 0,  -- 单位：秒
            window_title TEXT,
            process_name TEXT,
            process_path TEXT,
            pid INTEGER,
            hwnd INTEGER,
            cpu_percent REAL,
            memory_mb REAL,
            category TEXT,
            is_idle INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- 屏幕分析扩展字段
            file_name TEXT DEFAULT '',
            project_name TEXT DEFAULT '',
            page_title TEXT DEFAULT '',
            context TEXT DEFAULT '',
            app_type TEXT DEFAULT '',
            screen_text TEXT DEFAULT '',
            task_type TEXT DEFAULT '',
            task_confidence REAL DEFAULT 0,
            app_context TEXT DEFAULT '',
            keywords TEXT DEFAULT '',
            screenshot_path TEXT DEFAULT ''
        )
    ''')
    
    # 增量迁移：为旧表添加新字段（如果不存在）
    new_columns = [
        ('file_name', 'TEXT DEFAULT ""'),
        ('project_name', 'TEXT DEFAULT ""'),
        ('page_title', 'TEXT DEFAULT ""'),
        ('context', 'TEXT DEFAULT ""'),
        ('app_type', 'TEXT DEFAULT ""'),
        ('screen_text', 'TEXT DEFAULT ""'),
        ('task_type', 'TEXT DEFAULT ""'),
        ('task_confidence', 'REAL DEFAULT 0'),
        ('app_context', 'TEXT DEFAULT ""'),
        ('keywords', 'TEXT DEFAULT ""'),
        ('screenshot_path', 'TEXT DEFAULT ""'),
    ]
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(activities)").fetchall()}
    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE activities ADD COLUMN {col_name} {col_type}")
    
    # 日报汇总表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_date DATE NOT NULL UNIQUE,
            total_active_seconds INTEGER DEFAULT 0,
            total_idle_seconds INTEGER DEFAULT 0,
            session_count INTEGER DEFAULT 0,
            top_apps TEXT,  -- JSON
            category_breakdown TEXT,  -- JSON
            report_path TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()


class ActivityDB:
    def __init__(self):
        self.db_path = DB_PATH
    
    def _connect(self):
        return sqlite3.connect(self.db_path)
    
    def insert_activity(self, activity: dict) -> int:
        """插入一条活动记录，返回记录ID"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO activities 
            (start_time, end_time, duration, window_title, process_name, 
             process_path, pid, hwnd, cpu_percent, memory_mb, category, is_idle,
             file_name, project_name, page_title, context, app_type,
             screen_text, task_type, task_confidence, app_context, keywords, screenshot_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            activity.get('start_time'),
            activity.get('end_time'),
            activity.get('duration', 0),
            activity.get('window_title', ''),
            activity.get('process_name', ''),
            activity.get('process_path', ''),
            activity.get('pid', 0),
            activity.get('hwnd', 0),
            activity.get('cpu_percent', 0.0),
            activity.get('memory_mb', 0.0),
            activity.get('category', '其他'),
            1 if activity.get('is_idle', False) else 0,
            activity.get('file_name', ''),
            activity.get('project_name', ''),
            activity.get('page_title', ''),
            activity.get('context', ''),
            activity.get('app_type', ''),
            activity.get('screen_text', ''),
            activity.get('task_type', ''),
            activity.get('task_confidence', 0.0),
            activity.get('app_context', ''),
            activity.get('keywords', ''),
            activity.get('screenshot_path', ''),
        ))
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return row_id
    
    def update_activity_end(self, activity_id: int, end_time: datetime, duration: int):
        """更新活动记录的结束时间和时长"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE activities SET end_time = ?, duration = ? WHERE id = ?
        ''', (end_time, duration, activity_id))
        conn.commit()
        conn.close()
    
    def get_activities_by_date(self, target_date: date) -> list:
        """获取某天的所有活动记录，对进行中的活动动态计算duration"""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM activities 
            WHERE date(start_time) = ?
            ORDER BY start_time ASC
        ''', (target_date.isoformat(),))
        now = datetime.now()
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            # 动态计算 duration：如果没有 end_time，用当前时间
            if d.get("end_time") is None and d.get("start_time") is not None:
                st = d["start_time"]
                if isinstance(st, str):
                    st = datetime.fromisoformat(st)
                d["duration"] = max(int((now - st).total_seconds()), 1)
                d["end_time"] = now.isoformat()
            rows.append(d)
        conn.close()
        return rows
    
    def get_date_range_activities(self, start_date: date, end_date: date) -> list:
        """获取日期范围内的活动记录"""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM activities 
            WHERE date(start_time) BETWEEN ? AND ?
            ORDER BY start_time ASC
        ''', (start_date.isoformat(), end_date.isoformat()))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_daily_stats(self, target_date: date) -> dict:
        """获取某天的统计信息
        
        注意：由于 _update_current_duration 每30秒将进行中活动的 duration 写入数据库，
        这里直接 SUM(duration) 即可得到准确结果，无需再对 end_time IS NULL 做补偿。
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        # 总活跃时间（直接SUM duration，已包含进行中活动的实时时长）
        cursor.execute('''
            SELECT COALESCE(SUM(duration), 0) FROM activities 
            WHERE date(start_time) = ? AND is_idle = 0
        ''', (target_date.isoformat(),))
        active_seconds = cursor.fetchone()[0] or 0
        
        # 总空闲时间
        cursor.execute('''
            SELECT COALESCE(SUM(duration), 0) FROM activities 
            WHERE date(start_time) = ? AND is_idle = 1
        ''', (target_date.isoformat(),))
        idle_seconds = cursor.fetchone()[0] or 0
        
        # 各应用使用时长排行
        cursor.execute('''
            SELECT process_name, window_title, SUM(duration) as total_duration
            FROM activities 
            WHERE date(start_time) = ? AND is_idle = 0 
              AND process_name != '' AND process_name != 'unknown'
            GROUP BY process_name
            ORDER BY total_duration DESC
            LIMIT 10
        ''', (target_date.isoformat(),))
        top_apps = [
            {"process": row[0], "title": row[1], "seconds": row[2]}
            for row in cursor.fetchall()
        ]
        
        # 各分类使用时长
        cursor.execute('''
            SELECT category, SUM(duration) as total_duration
            FROM activities 
            WHERE date(start_time) = ? AND is_idle = 0
            GROUP BY category
            ORDER BY total_duration DESC
        ''', (target_date.isoformat(),))
        categories = [
            {"category": row[0] or "其他", "seconds": row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "date": target_date.isoformat(),
            "active_seconds": active_seconds,
            "idle_seconds": idle_seconds,
            "total_seconds": active_seconds + idle_seconds,
            "top_apps": top_apps,
            "categories": categories
        }
    
    def save_daily_summary(self, summary_date: date, stats: dict, report_path: str):
        """保存日报汇总"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO daily_summaries 
            (summary_date, total_active_seconds, total_idle_seconds, 
             session_count, top_apps, category_breakdown, report_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            summary_date.isoformat(),
            stats.get('active_seconds', 0),
            stats.get('idle_seconds', 0),
            len(stats.get('top_apps', [])),
            json.dumps(stats.get('top_apps', []), ensure_ascii=False),
            json.dumps(stats.get('categories', []), ensure_ascii=False),
            report_path
        ))
        conn.commit()
        conn.close()
    
    def get_all_dates(self) -> list:
        """获取所有有记录的日期"""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT date(start_time) as d 
            FROM activities 
            ORDER BY d DESC
        ''')
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        return dates
