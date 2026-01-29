"""
Rich Markdown 渲染工具
用于在终端中美观地渲染各节点生成的 Markdown 文档
"""
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from typing import Optional

# 全局 Console 实例
console = Console()

# 节点图标映射
NODE_ICONS = {
    "structure": "🏗️",
    "style": "🎨", 
    "planner": "📋",
    "worker": "👷",
    "test": "🧪",
    "report": "📝",
}

# 节点标题映射
NODE_TITLES = {
    "structure": "项目结构分析",
    "style": "全局风格检查",
    "planner": "任务分工规划",
    "worker": "代码审查报告",
    "test": "测试执行结果",
    "report": "最终综合报告",
}

def render_markdown(content: str, title: Optional[str] = None, 
                    node_type: Optional[str] = None, 
                    border_style: str = "blue") -> None:
    """
    在终端中渲染 Markdown 内容
    
    Args:
        content: Markdown 格式的内容
        title: 面板标题（可选）
        node_type: 节点类型，用于自动设置图标和标题
        border_style: 边框颜色样式
    """
    if not content or not content.strip():
        console.print("[dim]（无内容）[/dim]")
        return
    
    # 自动设置标题
    if title is None and node_type:
        icon = NODE_ICONS.get(node_type, "📄")
        node_title = NODE_TITLES.get(node_type, node_type)
        title = f"{icon} {node_title}"
    
    # 渲染 Markdown
    md = Markdown(content)
    
    if title:
        # 使用 Panel 包装，带标题
        panel = Panel(
            md,
            title=title,
            title_align="left",
            border_style=border_style,
            padding=(1, 2)
        )
        console.print(panel)
    else:
        console.print(md)


def render_section_header(title: str, icon: str = "📌") -> None:
    """渲染分节标题"""
    console.print()
    console.print(Rule(f"[bold cyan]{icon} {title}[/bold cyan]", style="cyan"))
    console.print()


def render_task_list(tasks: list) -> None:
    """渲染任务列表表格"""
    if not tasks:
        console.print("[dim]无任务[/dim]")
        return
    
    table = Table(title="📋 任务分工列表", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("任务名称", style="green")
    table.add_column("文件数", justify="center", style="yellow")
    table.add_column("语言", style="blue")
    
    for task in tasks:
        table.add_row(
            task.get("id", ""),
            task.get("name", ""),
            str(len(task.get("files", []))),
            task.get("language", "")
        )
    
    console.print(table)
    console.print()


def render_review_result(task_id: str, task_name: str, content: str) -> None:
    """渲染单个代码审查结果"""
    title = f"👷 代码审查: {task_name} ({task_id})"
    render_markdown(content, title=title, border_style="green")


def render_test_result(test_name: str, success: bool, output: str, 
                       script_content: Optional[str] = None) -> None:
    """渲染测试结果"""
    status = "[green]✅ PASS[/green]" if success else "[red]❌ FAIL[/red]"
    title = f"🧪 测试: {test_name} {status}"
    
    # 如果有脚本内容，先显示脚本
    if script_content and script_content.strip():
        console.print(Panel(
            Syntax(script_content[:1500], "bash", theme="monokai", line_numbers=True),
            title="📜 测试脚本",
            border_style="dim"
        ))
    
    # 显示输出
    border_color = "green" if success else "red"
    console.print(Panel(
        output[:3000] if output else "(无输出)",
        title=title,
        border_style=border_color
    ))


def render_test_summary(total: int, passed: int, failed: int) -> None:
    """渲染测试统计摘要"""
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    table = Table(title="🧪 测试统计", show_header=False, box=None)
    table.add_column("指标", style="bold")
    table.add_column("值", justify="right")
    
    table.add_row("总测试数", str(total))
    table.add_row("通过", f"[green]{passed}[/green]")
    table.add_row("失败", f"[red]{failed}[/red]" if failed > 0 else "0")
    table.add_row("通过率", f"[{'green' if pass_rate >= 80 else 'yellow' if pass_rate >= 50 else 'red'}]{pass_rate:.1f}%[/]")
    
    console.print(Panel(table, border_style="cyan"))


def render_progress(message: str, status: str = "working") -> None:
    """渲染进度信息"""
    icons = {
        "working": "⏳",
        "done": "✅",
        "error": "❌",
        "info": "ℹ️"
    }
    icon = icons.get(status, "•")
    console.print(f"  {icon} {message}")


def render_error(message: str) -> None:
    """渲染错误信息"""
    console.print(Panel(
        f"[red]{message}[/red]",
        title="❌ 错误",
        border_style="red"
    ))


def render_success(message: str) -> None:
    """渲染成功信息"""
    console.print(Panel(
        f"[green]{message}[/green]",
        title="✅ 成功",
        border_style="green"
    ))


def print_banner() -> None:
    """打印程序启动 Banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           🔍 Complex Code Review System V2.0 🔍              ║
║                 代码审查与测试分析系统                         ║
╚══════════════════════════════════════════════════════════════╝
    """
    console.print(Text(banner, style="bold cyan"))
