"""
窗口标题解析模块 - 从应用窗口标题中提取结构化上下文信息

支持的应用格式：
- 编辑器(TRAE/VS Code/Cursor/IDEA/PyCharm): "文件名 - 项目名 - TRAE"
- 浏览器(Chrome/Edge): "页面标题 - 浏览器名"
- 办公软件(Word/Excel/WPS): "文档名 - Word"
"""
import re


def parse_window_title(title: str, process_name: str) -> dict:
    """
    解析窗口标题，提取结构化上下文信息
    
    Returns:
        dict: {
            "raw_title": 原始标题,
            "file_name": 当前文件/文档名,
            "project_name": 项目/工作区名,
            "page_title": 页面标题(浏览器),
            "context": 一句话描述当前在做什么,
            "app_type": 应用类型(editor/browser/office/other)
        }
    """
    proc = process_name.lower()
    result = {
        "raw_title": title,
        "file_name": "",
        "project_name": "",
        "page_title": "",
        "context": title[:60],
        "app_type": "other"
    }
    
    # ========== 编辑器类 ==========
    editor_patterns = [
        # TRAE / VS Code / Cursor / Sublime: "文件名 - 项目名 - TRAE"
        # 示例: "main.py - work_tracker - TRAE"
        r"^(.*?)\s+-\s+(.*?)\s+-\s+(TRAÉ|TRAE|VS Code|Cursor|Code)$",
        # 带方括号的编辑器: "文件名 [项目名] - PyCharm"
        r"^(.*?)\s+\[(.*?)\]\s+-\s+(.*)$",
        # 简单格式: "文件名 - TRAE"
        r"^(.*?)\s+-\s+(TRAÉ|TRAE|VS Code|Cursor|Code|Notepad\+\+|Sublime Text)$",
        # 括号格式: "文件名 (项目名) - TRAE"
        r"^(.*?)\s+\((.*?)\)\s+-\s+(.*)$",
    ]
    
    for pattern in editor_patterns:
        match = re.match(pattern, title)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                result["file_name"] = groups[0].strip()
                if len(groups) >= 3:
                    result["project_name"] = groups[1].strip()
                    result["context"] = f"编辑 {groups[0]} ({groups[1]})"
                else:
                    result["project_name"] = groups[1].strip() if len(groups) > 1 else ""
                    result["context"] = f"编辑 {groups[0]}"
            result["app_type"] = "editor"
            return result
    
    # ========== 浏览器类 ==========
    browser_keywords = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"]
    if proc in browser_keywords:
        result["app_type"] = "browser"
        # "页面标题 - 浏览器名" 或 "页面标题 - 用户配置 - Edge"
        parts = title.split(" - ")
        if len(parts) >= 2:
            result["page_title"] = parts[0].strip()
            result["context"] = f"浏览: {parts[0][:40]}"
        else:
            result["page_title"] = title.strip()
            result["context"] = f"浏览: {title[:40]}"
        return result
    
    # ========== 办公软件 ==========
    office_patterns = [
        # Word/WPS: "文档名 - Word"
        (r"^(.*?)\s+-\s+(Word|WPS文字|Microsoft Word)$", "文档编辑"),
        # Excel: "文件名 - Excel"
        (r"^(.*?)\s+-\s+(Excel|WPS表格|Microsoft Excel)$", "表格处理"),
        # PowerPoint: "演示名 - PowerPoint"
        (r"^(.*?)\s+-\s+(PowerPoint|WPS演示|Microsoft PowerPoint)$", "演示编辑"),
        # PDF: "文件名 - Adobe Acrobat"
        (r"^(.*?)\s+-\s+(Adobe Acrobat|SumatraPDF|Foxit Reader)$", "阅读PDF"),
    ]
    
    for pattern, action in office_patterns:
        match = re.match(pattern, title)
        if match:
            result["file_name"] = match.group(1).strip()
            result["context"] = f"{action}: {match.group(1)}"
            result["app_type"] = "office"
            return result
    
    # ========== 通讯工具 ==========
    chat_keywords = ["wechat.exe", "dingtalk.exe", "lark.exe", "feishu.exe", "qq.exe", "tim.exe", "wechatappex.exe"]
    if proc in chat_keywords:
        result["app_type"] = "chat"
        # 尝试提取聊天对象
        if " - " in title:
            parts = title.split(" - ")
            if len(parts) >= 2:
                result["context"] = f"聊天: {parts[0][:30]}"
            else:
                result["context"] = f"聊天中: {title[:30]}"
        else:
            result["context"] = f"通讯工具: {title[:30]}"
        return result
    
    # ========== 数据库工具 ==========
    db_keywords = ["navicat.exe", "datagrip64.exe", "heidisql.exe", "dbeaver.exe"]
    if proc in db_keywords:
        result["app_type"] = "database"
        if " - " in title:
            parts = title.split(" - ")
            result["context"] = f"数据库: {parts[0][:40]}"
        return result
    
    # ========== 设计工具 ==========
    design_keywords = ["photoshop.exe", "illustrator.exe", "figma.exe", "eagle.exe", "sketch.exe"]
    if proc in design_keywords:
        result["app_type"] = "design"
        if " - " in title:
            parts = title.split(" - ")
            result["file_name"] = parts[0].strip()
            result["context"] = f"设计: {parts[0][:40]}"
        return result
    
    # ========== 终端/远程 ==========
    terminal_keywords = ["xshell.exe", "mstsc.exe", "termius.exe", "windows terminal"]
    if proc in terminal_keywords:
        result["app_type"] = "terminal"
        result["context"] = f"终端: {title[:40]}"
        return result
    
    # ========== 通用分割解析 ==========
    if " - " in title:
        parts = title.split(" - ")
        if len(parts) >= 2:
            result["file_name"] = parts[0].strip()
            result["project_name"] = parts[1].strip() if len(parts) > 1 else ""
            result["context"] = f"{parts[0][:30]} ({parts[1][:20]})"
    
    return result


def get_enriched_description(activity: dict) -> str:
    """
    为活动记录生成更丰富的描述
    
    Args:
        activity: 包含 window_title 和 process_name 的活动字典
    
    Returns:
        str: 富化的描述文本
    """
    title = activity.get("window_title", "")
    proc = activity.get("process_name", "")
    category = activity.get("category", "其他")
    
    parsed = parse_window_title(title, proc)
    
    # 构建描述
    parts = []
    
    if parsed["file_name"]:
        parts.append(f"文件: {parsed['file_name']}")
    if parsed["project_name"]:
        parts.append(f"项目: {parsed['project_name']}")
    if parsed["page_title"]:
        parts.append(f"页面: {parsed['page_title']}")
    
    if parts:
        return " | ".join(parts)
    
    # 如果解析失败，返回原始标题截断版
    return title[:50] if title else "未知操作"
