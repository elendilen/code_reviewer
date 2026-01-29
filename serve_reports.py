#!/usr/bin/env python3
"""
单独启动报告 Web 服务器
用于查看已生成的报告，无需重新运行审查
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.report_server import start_server

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="启动报告 Web 服务器")
    parser.add_argument("-p", "--port", type=int, default=8080, help="服务器端口 (默认: 8080)")
    parser.add_argument("-d", "--dir", default="reports", help="报告目录 (默认: reports)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()
    
    if not os.path.exists(args.dir):
        print(f"❌ 报告目录不存在: {args.dir}")
        print("   请先运行 main.py 生成报告")
        sys.exit(1)
    
    start_server(reports_dir=args.dir, port=args.port, open_browser=not args.no_browser)
