# WorkTracker

> AI 驱动的桌面活动监控与工作日报系统 | TRAE AI 创造力大赛参赛作品

<p align="center">
  <strong>赛道：学习工作</strong> &nbsp;|&nbsp; <strong>全程使用 TRAE Work 辅助开发</strong>
</p>

---

## 简介

WorkTracker 是一个 **全自动、零负担** 的桌面活动追踪工具。它在后台静默运行，自动识别你在做什么、做了多久，一键生成结构化的工作日报。

**你只管工作，记录交给 AI。**

## 核心功能

| 功能 | 说明 |
|------|------|
| 实时活动追踪 | 每 10 秒采样前台窗口，精确到秒的时长统计 |
| AI 任务识别 | 50+ 进程智能分类，UI Automation 提取窗口文字识别具体任务类型 |
| 可视化面板 | Web Dashboard 实时展示类别分布、应用排行、活动时间线 |
| 一键日报/周报 | 自动汇总生成精美 HTML 报告，支持打印为 PDF |
| OA 系统对接 | 预配置 OA 地址，日报一键填充提交 |
| 本地隐私优先 | 所有数据存储在本地 SQLite，不上传云端 |
| 开机自启 | 支持任务计划程序/Windows 服务两种自启方式 |
| 单文件 EXE | PyInstaller 打包，双击即用，无需安装 Python |

## 快速开始

### 方式一：下载 EXE（推荐）

1. 前往 [Releases](../../releases) 下载最新版 `WorkTracker.exe`
2. 双击运行，浏览器自动打开 `http://127.0.0.1:5678`
3. 点击「启动监控」开始使用

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/yourname/WorkTracker.git
cd WorkTracker

# 安装依赖
pip install -r requirements.txt

# 启动
python web_gui.py
```

打开浏览器访问 `http://127.0.0.1:5678`

## 使用指南

### 日常使用

1. **启动监控** — 打开 Web 面板，点击「启动监控」按钮
2. **正常工作** — WorkTracker 在后台自动记录你的桌面活动
3. **查看数据** — 控制面板实时展示今日统计、时间线、应用排行
4. **生成日报** — 到「日报生成」页面，选择日期，一键生成 HTML 日报
5. **提交 OA**（可选）— 在「OA 提交」页面配置 OA 地址，日报自动填充

### 开机自启

双击 `设置开机自启.bat`，通过 Windows 任务计划程序实现登录后自动启动。

### 打包 EXE

```bash
pip install pyinstaller
pyinstaller worktracker.spec --clean --noconfirm
# 生成 dist/WorkTracker.exe
```

## 技术架构

```
┌─────────────────────────────────────────┐
│           Flask Web GUI (HTTP)           │
│    Dashboard / Timeline / Reports        │
├─────────────────────────────────────────┤
│         SQLite Database (本地)           │
│    activities / daily_summaries          │
├─────────────────────────────────────────┤
│      ScreenAnalyzer + ActivityParser     │
│    UI Automation / 关键词分类 / 上下文提取  │
├─────────────────────────────────────────┤
│         ActivityMonitor (核心)            │
│    Win32 API / psutil / 空闲检测          │
└─────────────────────────────────────────┘
```

| 层级 | 技术栈 |
|------|--------|
| 数据采集 | Python, win32gui, win32process, psutil |
| 智能分析 | UI Automation COM, 正则匹配, 关键词分类 |
| 持久层 | SQLite, 增量迁移设计 |
| 展示层 | Flask, HTML/CSS/JS, 递归 setTimeout 自动刷新 |
| 打包分发 | PyInstaller (单文件 EXE) |

## 项目结构

```
WorkTracker/
├── web_gui.py              # Flask Web 服务
├── monitor.py              # 核心监控模块
├── database.py             # SQLite 数据库层
├── screen_analyzer.py      # 屏幕内容分析
├── activity_parser.py      # 窗口标题解析
├── reporter.py             # 日报/周报生成
├── config.py               # 全局配置
├── run.py                  # EXE 启动入口
├── service_installer.py    # Windows 服务安装器
├── worktracker.spec        # PyInstaller 打包配置
├── requirements.txt        # Python 依赖
├── static/
│   └── index.html          # Web 前端单页应用
├── data/                   # 运行时数据（自动创建）
│   ├── work_tracker.db     # SQLite 数据库
│   └── screenshots/        # 窗口缩略图
├── reports/                # 生成的日报（自动创建）
├── dist/                   # 打包输出（自动创建）
│   └── WorkTracker.exe
├── worktracker-trae-contest/
│   └── WorkTracker-standalone.html  # 大赛介绍页
├── 设置开机自启.bat         # 一键开机自启
├── 服务管理.bat             # Windows 服务管理
└── README.md
```

## 隐私说明

- **纯本地运行** — 所有数据存储在本地 SQLite 数据库，不上传任何云端
- **不记录敏感内容** — 不对全屏做 OCR，不记录密码框内容
- **截图受限** — 仅保留 320x180 缩略图，最多 30 张自动清理
- **完全开源** — 代码可审计，可自行修改编译

## TRAE AI 创造力大赛

- **赛道**：学习工作
- **工具**：TRAE Work（全程辅助开发）
- **介绍页**：[WorkTracker-standalone.html](worktracker-trae-contest/WorkTracker-standalone.html)

## License

MIT License - 详见 [LICENSE](LICENSE)
