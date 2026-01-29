import warnings
# 抑制 Pydantic V1 与 Python 3.14 不兼容的警告
warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality")

import sys
import os
import argparse
import shlex
from src.graph.workflow import create_workflow
from src.utils.rich_renderer import (
    print_banner, render_success, render_error, 
    render_section_header, console
)
from rich.panel import Panel

def main():
    parser = argparse.ArgumentParser(
        description="Complex Code Review System V2 - 代码审查与测试分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本审查（无测试）
  python main.py /path/to/project

  # 指定测试命令
  python main.py /path/to/project -t "make test" -t "./run_tests.sh"

  # 指定测试目录（运行目录中所有脚本）
  python main.py /path/to/project --test-dir scripts/

  # 启用深度性能分析
  python main.py /path/to/project --perf

  # 完整分析（性能分析 + 动态剖析）
  python main.py /path/to/project --perf --profile

  # 审查完成后启动 Web 服务器查看报告
  python main.py /path/to/project --perf --serve
        """
    )
    parser.add_argument("project_path", help="要审查的项目路径")
    parser.add_argument("-t", "--test", action="append", dest="test_commands",
                        help="自定义测试命令（可多次使用）")
    parser.add_argument("--test-dir", dest="test_dir", default="",
                        help="测试目录路径（运行其中所有脚本）")
    parser.add_argument("--perf", action="store_true", dest="enable_perf",
                        help="启用深度性能分析（热点检测、内存分析、优化建议）")
    parser.add_argument("--profile", action="store_true", dest="enable_profiling",
                        help="启用动态性能剖析（需要可执行文件；可用 --exec/--exec-arg 指定运行方式）")
    parser.add_argument("--exec", dest="profiling_executable", default=None,
                        help="动态剖析时指定可执行文件路径（默认自动在项目中查找）")
    parser.add_argument("--exec-arg", action="append", dest="profiling_exec_args", default=None,
                        help="动态剖析时传给可执行文件的参数（可多次使用）")
    parser.add_argument("--exec-args", dest="profiling_exec_args_str", default=None,
                        help="动态剖析时传给可执行文件的参数字符串（会用 shlex 拆分）")
    parser.add_argument("--exec-cwd", dest="profiling_cwd", default=None,
                        help="动态剖析运行工作目录（默认项目根目录）")
    parser.add_argument("--serve", action="store_true", dest="serve_reports",
                        help="审查完成后启动 Web 服务器查看报告")
    parser.add_argument("--port", type=int, default=8080,
                        help="Web 服务器端口 (默认: 8080)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="安静模式，不渲染中间结果")
    args = parser.parse_args()
    
    # 打印启动 Banner
    print_banner()
    
    abs_path = os.path.abspath(args.project_path)
    if not os.path.exists(abs_path):
        render_error(f"路径不存在: {abs_path}")
        return

    # 显示配置信息
    perf_status = "✅ 启用" if args.enable_perf else "❌ 禁用"
    profile_status = "✅ 启用" if args.enable_profiling else "❌ 禁用"

    profiling_args: list[str] = []
    if args.profiling_exec_args_str:
        profiling_args.extend(shlex.split(args.profiling_exec_args_str))
    if args.profiling_exec_args:
        profiling_args.extend(args.profiling_exec_args)

    config_info = f"""[bold]项目路径:[/bold] {abs_path}
[bold]测试命令:[/bold] {args.test_commands or '未指定'}
[bold]测试目录:[/bold] {args.test_dir or '未指定'}
[bold]性能分析:[/bold] {perf_status}
[bold]动态剖析:[/bold] {profile_status}
[bold]剖析可执行文件:[/bold] {args.profiling_executable or '自动查找'}
[bold]剖析运行参数:[/bold] {profiling_args or '未指定'}
[bold]剖析工作目录:[/bold] {args.profiling_cwd or '项目根目录'}"""
    
    console.print(Panel(config_info, title="⚙️ 运行配置", border_style="cyan"))
    console.print()
    
    app = create_workflow()
    
    # 收集自定义测试配置
    custom_tests = args.test_commands or []
    test_dir = args.test_dir
    
    initial_state = {
        "project_path": abs_path,
        "messages": [],
        "readme_content": "",  # 将由 structure_agent 填充
        "structure_doc": "",
        "global_style_report": "",
        "tasks": [],
        "reviews": [],
        "test_results": [],
        "performance_report": "",
        "final_report": "",
        "custom_test_commands": custom_tests,
        "test_dir": test_dir,
        "enable_performance_analysis": args.enable_perf,
        "enable_profiling": args.enable_profiling,
        "profiling_executable": args.profiling_executable,
        "profiling_args": profiling_args,
        "profiling_cwd": args.profiling_cwd
    }
    
    try:
        final_state = app.invoke(initial_state)
        
        # Save output - 只保存三个核心文档
        os.makedirs("reports", exist_ok=True)
        
        # 1. 项目结构、核心算法和数据结构介绍
        with open("reports/project_structure.md", "w", encoding="utf-8") as f:
            f.write(final_state.get("structure_doc", ""))
        
        # 2. 性能分析结果及优化方向
        perf_report = final_state.get("performance_report", "")
        if perf_report:
            with open("reports/performance_analysis.md", "w", encoding="utf-8") as f:
                f.write(perf_report)
        
        # 3. 文件风格报告
        with open("reports/style_report.md", "w", encoding="utf-8") as f:
            f.write(final_state.get("global_style_report", ""))
        
        # 显示完成信息
        console.print()
        render_success(f"审查完成！报告已保存到 reports/ 目录")
        console.print()
        
        # 显示报告文件列表
        report_files = [
            ("项目结构与算法", "reports/project_structure.md"),
            ("风格检查", "reports/style_report.md"),
        ]
        
        if perf_report:
            report_files.insert(1, ("性能分析", "reports/performance_analysis.md"))
        
        console.print("[bold]📁 生成的报告文件:[/bold]")
        for name, path in report_files:
            abs_report_path = os.path.abspath(path)
            console.print(f"  • {name}: [link=file://{abs_report_path}]{path}[/link]")
        
        # 启动 Web 服务器
        if args.serve_reports:
            console.print()
            console.print(f"[bold cyan]🌐 启动 Web 服务器，端口: {args.port}[/bold cyan]")
            from src.utils.report_server import start_server
            start_server(reports_dir="reports", port=args.port, open_browser=True)
        
    except Exception as e:
        render_error(f"执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
