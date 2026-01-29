"""
报告 Web 服务器
将 Markdown 报告渲染为网页展示
"""

import os
import http.server
import socketserver
import threading
import webbrowser
from urllib.parse import unquote
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Code Review Reports</title>
    <link href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.2.0/github-markdown.min.css" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0d1117;
            --text-color: #c9d1d9;
            --border-color: #30363d;
            --link-color: #58a6ff;
            --header-bg: #161b22;
            --card-bg: #161b22;
            --accent-color: #238636;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }}
        
        .header {{
            background: var(--header-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 32px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        .header h1 {{
            font-size: 20px;
            font-weight: 600;
            color: #fff;
        }}
        
        .header nav {{
            margin-top: 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        .header nav a {{
            color: var(--text-color);
            text-decoration: none;
            padding: 6px 12px;
            border-radius: 6px;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            font-size: 14px;
            transition: all 0.2s;
        }}
        
        .header nav a:hover, .header nav a.active {{
            background: var(--accent-color);
            border-color: var(--accent-color);
            color: #fff;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px;
        }}
        
        .markdown-body {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 32px;
            color: var(--text-color);
        }}
        
        .markdown-body h1, .markdown-body h2, .markdown-body h3, 
        .markdown-body h4, .markdown-body h5, .markdown-body h6 {{
            color: #fff;
            border-bottom-color: var(--border-color);
        }}
        
        .markdown-body a {{
            color: var(--link-color);
        }}
        
        .markdown-body code {{
            background: rgba(110, 118, 129, 0.4);
            border-radius: 6px;
            padding: 0.2em 0.4em;
        }}
        
        .markdown-body pre {{
            background: #161b22 !important;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 16px;
            overflow-x: auto;
        }}
        
        .markdown-body pre code {{
            background: transparent;
            padding: 0;
        }}
        
        .markdown-body table {{
            border-collapse: collapse;
            width: 100%;
        }}
        
        .markdown-body table th, .markdown-body table td {{
            border: 1px solid var(--border-color);
            padding: 8px 12px;
        }}
        
        .markdown-body table th {{
            background: var(--header-bg);
        }}
        
        .markdown-body blockquote {{
            border-left: 4px solid var(--accent-color);
            color: #8b949e;
            padding-left: 16px;
        }}
        
        .index-page {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            padding: 32px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .report-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 24px;
            transition: all 0.2s;
        }}
        
        .report-card:hover {{
            border-color: var(--accent-color);
            transform: translateY(-2px);
        }}
        
        .report-card h3 {{
            color: #fff;
            margin-bottom: 8px;
            font-size: 18px;
        }}
        
        .report-card p {{
            color: #8b949e;
            font-size: 14px;
            margin-bottom: 16px;
        }}
        
        .report-card a {{
            color: var(--link-color);
            text-decoration: none;
            font-weight: 500;
        }}
        
        .report-card a:hover {{
            text-decoration: underline;
        }}
        
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            margin-right: 8px;
        }}
        
        .badge-green {{ background: #238636; color: #fff; }}
        .badge-yellow {{ background: #9e6a03; color: #fff; }}
        .badge-blue {{ background: #1f6feb; color: #fff; }}
        
        {pygments_css}
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 Code Review Reports</h1>
        <nav>
            <a href="/" {index_active}>首页</a>
            {nav_links}
        </nav>
    </div>
    {content}
</body>
</html>
"""

INDEX_TEMPLATE = """
<div class="index-page">
    {cards}
</div>
"""

CARD_TEMPLATE = """
<div class="report-card">
    <h3>{icon} {title}</h3>
    <p>{description}</p>
    <div style="margin-bottom: 12px;">
        {badges}
    </div>
    <a href="{link}">查看报告 →</a>
</div>
"""

REPORT_INFO = {
    "project_structure.md": {
        "title": "项目结构说明",
        "icon": "🏗️",
        "description": "项目目录结构、核心模块与关键实现概览",
        "badges": '<span class="badge badge-blue">结构</span>'
    },
    "performance_analysis.md": {
        "title": "性能分析报告",
        "icon": "⚡",
        "description": "热点分析、内存风险点与优化建议（可结合动态剖析指标）",
        "badges": '<span class="badge badge-yellow">性能</span><span class="badge badge-green">优化</span>'
    },
    "style_report.md": {
        "title": "代码风格检查",
        "icon": "🎨",
        "description": "代码规范、命名约定和风格一致性检查",
        "badges": '<span class="badge badge-blue">风格</span>'
    }
}


class ReportHandler(http.server.SimpleHTTPRequestHandler):
    """自定义请求处理器"""
    
    def __init__(self, *args, reports_dir="reports", **kwargs):
        self.reports_dir = reports_dir
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        path = unquote(self.path)
        
        if path == "/" or path == "/index.html":
            self.serve_index()
        elif path.endswith(".md"):
            self.serve_markdown(path[1:])  # 去掉开头的 /
        else:
            super().do_GET()
    
    def serve_index(self):
        """渲染首页"""
        cards = []
        nav_links = []
        
        for filename, info in REPORT_INFO.items():
            filepath = os.path.join(self.reports_dir, filename)
            if os.path.exists(filepath):
                cards.append(CARD_TEMPLATE.format(
                    icon=info["icon"],
                    title=info["title"],
                    description=info["description"],
                    badges=info["badges"],
                    link=f"/{filename}"
                ))
                nav_links.append(f'<a href="/{filename}">{info["icon"]} {info["title"]}</a>')
        
        if not cards:
            cards.append('<div class="report-card"><h3>暂无报告</h3><p>请先运行代码审查生成报告</p></div>')
        
        content = INDEX_TEMPLATE.format(cards="\n".join(cards))
        
        html = HTML_TEMPLATE.format(
            title="首页",
            content=content,
            nav_links="\n".join(nav_links),
            index_active='class="active"',
            pygments_css=HtmlFormatter(style='monokai').get_style_defs('.highlight')
        )
        
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def serve_markdown(self, filename):
        """渲染 Markdown 文件"""
        filepath = os.path.join(self.reports_dir, filename)
        
        if not os.path.exists(filepath):
            self.send_error(404, f"Report not found: {filename}")
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # 使用 Python-Markdown 渲染
        md = markdown.Markdown(extensions=[
            'fenced_code',
            'codehilite',
            'tables',
            'toc',
            'nl2br'
        ], extension_configs={
            'codehilite': {
                'css_class': 'highlight',
                'linenums': False,
                'guess_lang': True
            }
        })
        
        html_content = md.convert(md_content)
        
        # 构建导航链接
        nav_links = []
        for fname, info in REPORT_INFO.items():
            fpath = os.path.join(self.reports_dir, fname)
            if os.path.exists(fpath):
                active = 'class="active"' if fname == filename else ''
                nav_links.append(f'<a href="/{fname}" {active}>{info["icon"]} {info["title"]}</a>')
        
        info = REPORT_INFO.get(filename, {"title": filename, "icon": "📄"})
        
        content = f'<div class="container"><div class="markdown-body">{html_content}</div></div>'
        
        html = HTML_TEMPLATE.format(
            title=info["title"],
            content=content,
            nav_links="\n".join(nav_links),
            index_active='',
            pygments_css=HtmlFormatter(style='monokai').get_style_defs('.highlight')
        )
        
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        """静默日志或自定义输出"""
        pass


def create_handler(reports_dir):
    """创建带参数的处理器"""
    def handler(*args, **kwargs):
        return ReportHandler(*args, reports_dir=reports_dir, **kwargs)
    return handler


def start_server(reports_dir="reports", port=8080, open_browser=True):
    """启动报告服务器"""
    handler = create_handler(os.path.abspath(reports_dir))
    
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"\n🌐 报告服务器已启动: {url}")
        print(f"   按 Ctrl+C 停止服务器\n")
        
        if open_browser:
            webbrowser.open(url)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")


def start_server_background(reports_dir="reports", port=8080, open_browser=True):
    """在后台线程启动服务器"""
    thread = threading.Thread(
        target=start_server,
        kwargs={"reports_dir": reports_dir, "port": port, "open_browser": open_browser},
        daemon=True
    )
    thread.start()
    return thread


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="报告 Web 服务器")
    parser.add_argument("-p", "--port", type=int, default=8080, help="服务器端口")
    parser.add_argument("-d", "--dir", default="reports", help="报告目录")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()
    
    start_server(args.dir, args.port, not args.no_browser)
