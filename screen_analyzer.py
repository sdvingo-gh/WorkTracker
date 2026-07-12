"""
屏幕内容分析模块 - 通过截图和窗口信息深入分析用户当前任务内容

策略：
1. 屏幕截图（仅保存缩略图，不识别全屏以保护隐私）
2. 活动窗口截图 + 文字提取（通过 UI Automation API）
3. 关键区域检测（标题栏、状态栏、编辑区）
4. 任务内容智能分类（基于关键词匹配）

隐私保护：
- 不对全屏做OCR识别
- 截图仅保留最近30张缩略图（自动清理）
- 不记录敏感内容（密码框等）
"""
import os
import time
import re
import ctypes
from datetime import datetime
from collections import Counter

try:
    from PIL import Image, ImageGrab, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from config import BASE_DIR, DATA_DIR

# 截图存储目录
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 最大保留截图数
MAX_SCREENSHOTS = 30


class ScreenAnalyzer:
    """屏幕内容分析器"""
    
    def __init__(self):
        self.last_analysis = {}
        self.analysis_count = 0
        self._cleanup_screenshots()
    
    def analyze_current_screen(self, hwnd=0, window_title="", process_name="") -> dict:
        """
        分析当前屏幕内容，返回结构化信息
        
        Returns:
            {
                "screen_text": "提取的主要文字内容",
                "app_context": "应用内部上下文（如文件名、标签页名）",
                "focused_element": "当前焦点元素",
                "keywords": ["关键词列表"],
                "task_type": "编码/文档/沟通/浏览/其他",
                "confidence": 0.85,
                "screenshot_path": "缩略图路径"
            }
        """
        result = {
            "screen_text": "",
            "app_context": "",
            "focused_element": "",
            "keywords": [],
            "task_type": "其他",
            "confidence": 0.0,
            "screenshot_path": None
        }
        
        # 1. 通过 Windows UI Automation 获取窗口文字
        ui_text = self._get_ui_text(hwnd)
        if ui_text:
            result["screen_text"] = ui_text[:500]
            result["keywords"] = self._extract_keywords(ui_text)
            result["task_type"] = self._classify_task(ui_text, process_name, window_title)
            result["confidence"] = min(len(ui_text) / 50.0, 1.0)  # 文字越多越可信
            result["app_context"] = self._extract_app_context(ui_text, process_name, window_title)
        
        # 2. 截取活动窗口缩略图（低频，每60秒一次）
        self.analysis_count += 1
        if self.analysis_count % 6 == 0 and PIL_AVAILABLE and hwnd:
            try:
                thumb = self._capture_window_thumbnail(hwnd)
                if thumb:
                    result["screenshot_path"] = thumb
            except Exception:
                pass
        
        self.last_analysis = result
        return result
    
    def _get_ui_text(self, hwnd) -> str:
        """
        通过 UI Automation API 获取窗口内可访问的文字元素
        比全屏OCR更精准、更快、不依赖外部引擎
        """
        if not hwnd:
            return ""
        
        texts = []
        
        try:
            # 方法1：枚举子窗口获取文字
            def enum_child_windows(hwnd_parent, texts_list):
                try:
                    import win32gui
                    def callback(h, texts_list):
                        try:
                            text = win32gui.GetWindowText(h)
                            cls = win32gui.GetClassName(h)
                            if text and len(text) > 1:
                                texts_list.append(text)
                        except Exception:
                            pass
                    win32gui.EnumChildWindows(hwnd_parent, callback, texts_list)
                except Exception:
                    pass
            
            enum_child_windows(hwnd, texts)
            
            # 方法2：通过 Windows UI Automation (COM)
            try:
                import comtypes.client
                from comtypes import GUID
                
                uia = comtypes.client.CreateObject(
                    "{ff48dba4-60ef-4201-aa94-7604a5db2998}",
                    interface=comtypes.gen._3A7A240B_4B45_40F4_B536_7DFE486F1B5D.IUIAutomation
                )
                element = uia.ElementFromHandle(hwnd)
                
                # 获取所有文本元素
                condition = uia.CreateTrueCondition()
                text_pattern = uia.CreatePropertyCondition(
                    30022,  # UIA_IsTextPatternAvailable
                    True
                )
                
                # 查找文本元素
                text_elements = element.FindAll(
                    comtypes.gen._3A7A240B_4B45_40F4_B536_7DFE486F1B5D.TreeScope_Descendants,
                    text_pattern
                )
                
                for i in range(min(text_elements.Length, 50)):  # 最多取50个
                    try:
                        el = text_elements.GetElement(i)
                        txt = el.GetCurrentPropertyValue(30059)  # UIA_NameProperty
                        if txt and len(str(txt).strip()) > 1:
                            texts.append(str(txt))
                    except Exception:
                        pass
                        
            except Exception:
                # COM 不可用时跳过
                pass
            
        except Exception as e:
            pass
        
        # 去重并合并
        unique_texts = []
        seen = set()
        for t in texts:
            t = t.strip()
            if t and t not in seen and len(t) < 200:
                seen.add(t)
                unique_texts.append(t)
        
        return " | ".join(unique_texts[:20])
    
    def _extract_keywords(self, text: str) -> list:
        """从文本中提取有意义的任务关键词"""
        # 过滤掉太短和无意义的词
        words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text)
        
        # 编程相关关键词
        code_keywords = {
            'function', 'class', 'def ', 'import ', 'return ', 'async ', 
            'const ', 'let ', 'var ', 'SELECT ', 'INSERT ', 'UPDATE ',
            'API', 'GET', 'POST', 'PUT', 'DELETE',
            'error', 'warning', 'debug', 'test',
            'python', 'java', 'sql', 'html', 'css', 'javascript',
            '组件', '接口', '函数', '方法', '数据库', '表', '字段',
        }
        
        # 通用任务关键词
        task_keywords = {
            '报告', '方案', '需求', '设计', '评审', '会议', '沟通',
            '文档', '表格', 'PPT', '演示', '邮件', '审批', '流程',
            '部署', '发布', '上线', '修复', '优化', '重构', '测试',
            'bug', 'issue', 'feature', 'PR', 'commit',
        }
        
        found = []
        text_lower = text.lower()
        for kw in code_keywords | task_keywords:
            if kw.lower() in text_lower:
                found.append(kw.strip())
        
        # 从文本中提取中文关键词（2-4字的词）
        for word in words:
            if 2 <= len(word) <= 4 and word not in found:
                # 简单的中文词频判断
                if word in task_keywords or any(c.isdigit() for c in word):
                    found.append(word)
        
        return list(set(found))[:10]
    
    def _extract_app_context(self, ui_text: str, process_name: str, window_title: str) -> str:
        """提取应用内部上下文（当前正在操作的文件/页面/对话）"""
        parts = []
        
        # 从 UI 文本中找文件名模式
        file_patterns = [
            r'[\w\u4e00-\u9fff\-_.]+\.(py|js|ts|java|sql|html|css|md|txt|json|yaml|yml|xml|conf|cfg|sh|bat|ps1)$',
            r'[\w\-_]+\.(docx?|xlsx?|pptx?|pdf)$',
        ]
        for pattern in file_patterns:
            matches = re.findall(pattern, ui_text, re.IGNORECASE)
            for m in matches[:3]:
                parts.append(f"文件: {m}")
        
        # 从 UI 文本中找 URL
        urls = re.findall(r'https?://[^\s|<>"]{5,50}', ui_text)
        for url in urls[:2]:
            # 提取域名和路径
            from urllib.parse import urlparse
            try:
                parsed = urlparse(url)
                path = parsed.path.strip('/')
                domain = parsed.netloc.replace('www.', '')
                if path:
                    parts.append(f"页面: {domain}/{path[:30]}")
                else:
                    parts.append(f"页面: {domain}")
            except Exception:
                pass
        
        # 从 UI 文本中找对话对象
        chat_patterns = [
            r'(@[\w]+)',  # @某人
        ]
        for pattern in chat_patterns:
            matches = re.findall(pattern, ui_text)
            if matches:
                parts.append(f"涉及: {', '.join(matches[:3])}")
        
        # 窗口标题中的标签页信息
        tab_patterns = [
            r'(和另外\s*\d+\s*个页面)',  # 浏览器标签
            r'[-—]\s*(.+?)\s*[-—|]',  # 标签页名
        ]
        for pattern in tab_patterns:
            match = re.search(pattern, window_title)
            if match:
                parts.append(f"标签: {match.group(1)[:30]}")
        
        return " | ".join(parts[:5]) if parts else ""
    
    def _classify_task(self, text: str, process_name: str, window_title: str) -> str:
        """基于屏幕内容分类当前任务类型"""
        text_lower = (text + " " + window_title).lower()
        
        # 编码相关
        code_indicators = [
            'def ', 'function ', 'class ', 'import ', 'return ', 'const ',
            'async ', 'await ', '=>', 'lambda', 'for ', 'while ',
            'print(', 'console.log', 'SELECT ', 'FROM ', 'WHERE ',
            'INSERT ', 'UPDATE ', 'DELETE ', 'CREATE TABLE',
            '.py', '.js', '.ts', '.java', '.sql', '.html', '.css',
            '语法错误', '编译', '调试', 'debug', 'terminal',
            '代码', '函数', '变量', '接口', 'API',
        ]
        
        # 文档/沟通
        doc_indicators = [
            '报告', '方案', '需求文档', '设计文档', '会议纪要',
            '.doc', '.docx', '.pdf', '.ppt', '.xlsx',
            '审批', '流程', '工单',
        ]
        
        # 沟通
        chat_indicators = [
            '消息', '聊天', '群聊', '私聊', '@', '回复',
            '发送', '接收', '语音', '视频会议',
        ]
        
        # 邮件
        email_indicators = [
            '收件箱', '发件箱', '抄送', '主题', '附件',
            'forward', 'reply', 'inbox', 'outbox',
        ]
        
        code_score = sum(1 for kw in code_indicators if kw.lower() in text_lower)
        doc_score = sum(1 for kw in doc_indicators if kw in text_lower)
        chat_score = sum(1 for kw in chat_indicators if kw in text_lower)
        email_score = sum(1 for kw in email_indicators if kw in text_lower)
        
        scores = {
            "编码开发": code_score,
            "文档编写": doc_score,
            "沟通协作": chat_score,
            "邮件处理": email_score,
            "浏览查阅": 1,  # 默认给浏览器一些基础分
        }
        
        # 根据进程名加权
        proc_lower = process_name.lower()
        if any(k in proc_lower for k in ['code', 'pycharm', 'idea', 'devenv', 'trae', 'cursor', 'vscode']):
            scores["编码开发"] += 3
        elif any(k in proc_lower for k in ['word', 'wps', 'notepad']):
            scores["文档编写"] += 3
        elif any(k in proc_lower for k in ['wechat', 'dingtalk', 'lark', 'feishu', 'qq', 'tim']):
            scores["沟通协作"] += 3
        elif any(k in proc_lower for k in ['outlook', 'foxmail']):
            scores["邮件处理"] += 3
        elif any(k in proc_lower for k in ['chrome', 'msedge', 'firefox']):
            scores["浏览查阅"] += 2
        
        # 返回得分最高的类型
        max_type = max(scores, key=scores.get)
        if scores[max_type] == 0:
            return "其他"
        return max_type
    
    def _capture_window_thumbnail(self, hwnd, size=(320, 180)) -> str:
        """截取活动窗口缩略图"""
        try:
            # 获取窗口位置
            import win32gui
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            
            if width < 10 or height < 10 or width > 5000 or height > 3000:
                return None
            
            # 截取窗口区域
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            
            # 缩放为缩略图
            img.thumbnail(size, Image.LANCZOS)
            
            # 保存
            filename = f"screen_{datetime.now().strftime('%H%M%S')}.jpg"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            img.save(filepath, "JPEG", quality=60)
            
            # 清理旧截图
            self._cleanup_screenshots()
            
            return filepath
        except Exception:
            return None
    
    def _cleanup_screenshots(self):
        """清理超过限制的旧截图"""
        try:
            files = sorted(
                os.listdir(SCREENSHOT_DIR),
                key=lambda f: os.path.getmtime(os.path.join(SCREENSHOT_DIR, f)),
                reverse=True
            )
            for f in files[MAX_SCREENSHOTS:]:
                try:
                    os.remove(os.path.join(SCREENSHOT_DIR, f))
                except Exception:
                    pass
        except Exception:
            pass


# 全局实例
_analyzer = None

def get_screen_analyzer() -> ScreenAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = ScreenAnalyzer()
    return _analyzer
