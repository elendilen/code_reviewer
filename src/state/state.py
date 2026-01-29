from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
import operator
from typing import Annotated

class Task(TypedDict):
    """定义单个分工任务"""
    id: str
    name: str
    files: List[str]
    description: str
    language: str

class ReviewResult(TypedDict):
    """定义审查结果"""
    task_id: str
    content: str  # Markdown 格式的局部检查报告
    issues: List[Dict[str, Any]]

class TestResult(TypedDict):
    """定义测试结果"""
    task_id: str
    test_files_generated: List[str]
    execution_output: str
    success: bool

class OverallState(TypedDict):
    """全局状态"""
    project_path: str
    # 消息历史，用于 Agent
    messages: Annotated[List[BaseMessage], operator.add]
    
    # README 文档内容（项目背景信息）
    readme_content: str
    
    # 用户自定义测试命令（可选）
    custom_test_commands: List[str]
    
    # 用户自定义测试目录（可选，运行其中所有脚本）
    test_dir: str
    
    # 是否启用性能分析
    enable_performance_analysis: bool
    
    # 是否启用动态性能剖析
    enable_profiling: bool

    # 动态剖析运行配置（可选）
    profiling_executable: Optional[str]
    profiling_args: List[str]
    profiling_cwd: Optional[str]
    
    # 项目结构分析结果
    structure_doc: str
    
    # 全局风格检查结果
    global_style_report: str
    
    # 任务分工列表
    tasks: List[Task]
    
    # 收集的审查结果 (Reduce 阶段使用)
    # 使用 operator.add 来合并并行分支的结果
    reviews: Annotated[List[ReviewResult], operator.add]
    
    # 收集的测试结果
    test_results: Annotated[List[TestResult], operator.add]
    
    # 性能分析报告
    performance_report: str
    
    # 最终报告
    final_report: str


class WorkerState(TypedDict):
    """并行 Worker 的子状态"""
    task: Task
    project_path: str
    readme_content: str  # 传递给 Worker 的项目背景信息
