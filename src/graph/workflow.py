from langgraph.graph import StateGraph, START, END
from ..state.state import OverallState, WorkerState
from ..agents.structure_agent import ProjectStructureAgent
from ..agents.style_agent import GlobalStyleAgent
from ..agents.planner_agent import PlannerAgent
from ..agents.worker_agent import WorkerAgent
from ..agents.test_runner import TestRunnerAgent
from ..agents.report_agent import FinalReportAgent
from ..utils.logger import workflow_logger as logger
from ..utils.rich_renderer import (
    render_markdown, render_section_header, render_task_list,
    render_review_result, render_test_summary, console
)
from ..performance.perf_workflow import run_performance_analysis, collect_source_files
from langgraph.constants import Send

# Initialize Agents
logger.info("初始化所有 Agents...")
structure_agent = ProjectStructureAgent()
style_agent = GlobalStyleAgent()
planner_agent = PlannerAgent()
worker_agent = WorkerAgent()
test_runner = TestRunnerAgent()
reporter = FinalReportAgent()
logger.info("Agents 初始化完成")

def analyze_structure(state: OverallState):
    logger.info("🔍 [节点] 开始执行: analyze_structure (项目结构分析)")
    result = structure_agent.analyze(state, None)
    
    # 使用 rich 渲染结构文档
    if result.get("structure_doc"):
        render_section_header("项目结构分析", "🏗️")
        render_markdown(result["structure_doc"], node_type="structure", border_style="blue")
    
    logger.info("✅ [节点] 完成: analyze_structure")
    return result

def check_global_style(state: OverallState):
    logger.info("🎨 [节点] 开始执行: check_global_style (全局风格检查)")
    result = style_agent.check(state)
    
    # 使用 rich 渲染风格报告
    if result.get("global_style_report"):
        render_section_header("全局风格检查", "🎨")
        render_markdown(result["global_style_report"], node_type="style", border_style="magenta")
    
    logger.info("✅ [节点] 完成: check_global_style")
    return result

def plan_tasks(state: OverallState):
    logger.info("📋 [节点] 开始执行: plan_tasks (任务分工)")
    result = planner_agent.plan(state)
    task_count = len(result.get('tasks', []))
    
    # 使用 rich 渲染任务列表
    if result.get("tasks"):
        render_section_header("任务分工规划", "📋")
        render_task_list(result["tasks"])
    
    logger.info(f"✅ [节点] 完成: plan_tasks - 分配了 {task_count} 个任务")
    return result

# Map step: Distribute tasks
def continue_to_verification(state: OverallState):
    tasks = state["tasks"]
    readme_content = state.get("readme_content", "")
    logger.info(f"🚀 [Map] 分发 {len(tasks)} 个并行任务到 Worker 节点")
    for i, task in enumerate(tasks):
        logger.info(f"   └─ Task {i+1}: {task.get('name', task.get('id', 'unknown'))}")
    # 将 readme_content 传递给每个 Worker
    return [Send("review_and_test_node", {
        "task": task, 
        "project_path": state["project_path"],
        "readme_content": readme_content
    }) for task in tasks]

# Worker Node - 只进行代码审查，测试由用户自定义
def worker_node(state: WorkerState):
    task = state["task"]
    task_name = task.get('name', task.get('id', 'unknown'))
    task_id = task.get('id', 'unknown')
    logger.info(f"👷 [Worker] 开始处理任务: {task_name}")
    
    # 只进行代码审查
    logger.info(f"   └─ 代码审查中...")
    review_update = worker_agent.review_code(state)
    
    # 使用 rich 渲染审查结果
    if review_update.get("reviews"):
        for review in review_update["reviews"]:
            render_section_header(f"代码审查: {task_name}", "👷")
            render_review_result(task_id, task_name, review.get("content", ""))
    
    logger.info(f"✅ [Worker] 任务完成: {task_name}")
    return review_update

def start_tests(state: OverallState):
    logger.info("🧪 [节点] 开始执行: run_tests (运行用户自定义测试)")
    logger.info(f"   └─ 收集到 {len(state.get('reviews', []))} 个审查结果")
    custom_cmds = state.get('custom_test_commands', [])
    test_dir = state.get('test_dir', '')
    logger.info(f"   └─ 自定义测试命令: {len(custom_cmds)} 个")
    logger.info(f"   └─ 测试目录: {test_dir or '未指定'}")
    result = test_runner.run_tests(state)
    
    # 使用 rich 渲染测试结果
    if result.get("test_results"):
        render_section_header("测试执行结果", "🧪")
        for test_res in result["test_results"]:
            if test_res.get("execution_output"):
                render_markdown(test_res["execution_output"], node_type="test", border_style="yellow")
    
    logger.info("✅ [节点] 完成: run_tests")
    return result


def run_performance_analysis_node(state: OverallState):
    """性能分析节点"""
    enable_perf = state.get("enable_performance_analysis", False)
    
    if not enable_perf:
        logger.info("⏭️ [节点] 跳过性能分析（未启用）")
        return {"performance_report": ""}
    
    logger.info("⚡ [节点] 开始执行: performance_analysis (深度性能分析)")
    
    project_path = state["project_path"]
    enable_profiling = state.get("enable_profiling", False)
    profiling_executable = state.get("profiling_executable")
    profiling_args = state.get("profiling_args") or []
    profiling_cwd = state.get("profiling_cwd")
    
    # 检测语言
    language = "c"  # 默认 C
    
    # 收集源文件
    source_files = collect_source_files(project_path, language)
    logger.info(f"   └─ 收集到 {len(source_files)} 个源文件")
    
    # 运行性能分析子图
    perf_state = run_performance_analysis(
        project_path=project_path,
        source_files=source_files,
        language=language,
        enable_profiling=enable_profiling,
        profiling_executable=profiling_executable,
        profiling_args=profiling_args,
        profiling_cwd=profiling_cwd
    )
    
    # 使用 rich 渲染性能报告
    if perf_state.get("performance_report"):
        render_section_header("深度性能分析报告", "⚡")
        render_markdown(perf_state["performance_report"], node_type="performance", border_style="red")
    
    logger.info("✅ [节点] 完成: performance_analysis")
    
    return {"performance_report": perf_state.get("performance_report", "")}

def generate_report(state: OverallState):
    logger.info("📝 [节点] 开始执行: generate_report (生成最终报告)")
    result = reporter.generate(state)
    
    # 使用 rich 渲染最终报告
    if result.get("final_report"):
        render_section_header("最终综合报告", "📝")
        render_markdown(result["final_report"], node_type="report", border_style="green")
    
    logger.info("✅ [节点] 完成: generate_report")
    return result

def create_workflow():
    workflow = StateGraph(OverallState)
    
    # Add Nodes
    workflow.add_node("analyze_structure", analyze_structure)
    workflow.add_node("check_global_style", check_global_style)
    workflow.add_node("plan_tasks", plan_tasks)
    workflow.add_node("review_and_test_node", worker_node)
    workflow.add_node("run_tests", start_tests)
    workflow.add_node("performance_analysis", run_performance_analysis_node)
    workflow.add_node("generate_report", generate_report)
    
    # Define Edges
    # 并行执行结构分析和全局风格检查
    workflow.add_edge(START, "analyze_structure")
    workflow.add_edge(START, "check_global_style")
    
    # 两个并行分支汇聚到 plan_tasks
    workflow.add_edge("analyze_structure", "plan_tasks")
    workflow.add_edge("check_global_style", "plan_tasks")
    
    # Conditional Edge for Map-Reduce
    # From plan_tasks, we "map" to review_and_test_node using Send
    workflow.add_conditional_edges(
        "plan_tasks", 
        continue_to_verification, 
        ["review_and_test_node"]
    )
    
    # After workers finish, run tests and performance analysis in parallel
    workflow.add_edge("review_and_test_node", "run_tests")
    workflow.add_edge("review_and_test_node", "performance_analysis")
    
    # Both converge to generate_report
    workflow.add_edge("run_tests", "generate_report")
    workflow.add_edge("performance_analysis", "generate_report")
    
    workflow.add_edge("generate_report", END)
    
    return workflow.compile()
