"""
Performance Analysis Workflow - 性能分析子图
组织所有性能分析 Agent 的工作流
"""
import os
from typing import List, Dict, Any
from langgraph.graph import StateGraph, START, END
from .perf_state import PerformanceState
from .code_extractor import CodeExtractorAgent
from .memory_analyzer import MemoryAnalyzerAgent
from .profiler_agent import ProfilerAgent
from .hotspot_detector import HotspotDetectorAgent
from .optimization_advisor import OptimizationAdvisorAgent
from ..utils.logger import setup_logger

logger = setup_logger("perf_workflow")

# 初始化所有 Agents
code_extractor = CodeExtractorAgent()
memory_analyzer = MemoryAnalyzerAgent()
profiler = ProfilerAgent()
hotspot_detector = HotspotDetectorAgent()
optimization_advisor = OptimizationAdvisorAgent()


def extract_code_node(state: PerformanceState) -> Dict[str, Any]:
    """代码提取节点"""
    logger.info("🔍 [性能分析] 开始代码结构提取")
    result = code_extractor.extract(state)
    logger.info(f"✅ [性能分析] 代码提取完成 - {len(result.get('functions', []))} 个函数")
    return result


def analyze_memory_node(state: PerformanceState) -> Dict[str, Any]:
    """内存分析节点"""
    logger.info("💾 [性能分析] 开始内存分析")
    result = memory_analyzer.analyze(state)
    logger.info(f"✅ [性能分析] 内存分析完成 - {len(result.get('memory_issues', []))} 个问题")
    return result


def profile_node(state: PerformanceState) -> Dict[str, Any]:
    """性能剖析节点"""
    logger.info("⏱️ [性能分析] 开始性能剖析")
    result = profiler.profile(state)
    if result.get("profiling_data"):
        logger.info(f"✅ [性能分析] 性能剖析完成")
    else:
        logger.info("⏭️ [性能分析] 性能剖析跳过（未启用或无可执行文件）")
    return result


def detect_hotspots_node(state: PerformanceState) -> Dict[str, Any]:
    """热点检测节点"""
    logger.info("🔥 [性能分析] 开始热点检测")
    result = hotspot_detector.detect(state)
    logger.info(f"✅ [性能分析] 热点检测完成 - {len(result.get('hotspots', []))} 个热点")
    return result


def generate_optimizations_node(state: PerformanceState) -> Dict[str, Any]:
    """优化建议生成节点"""
    logger.info("💡 [性能分析] 开始生成优化建议")
    result = optimization_advisor.advise(state)
    logger.info(f"✅ [性能分析] 优化建议生成完成 - {len(result.get('optimizations', []))} 条建议")
    return result


def create_performance_subgraph():
    """创建性能分析子图"""
    workflow = StateGraph(PerformanceState)
    
    # 添加节点
    workflow.add_node("extract_code", extract_code_node)
    workflow.add_node("analyze_memory", analyze_memory_node)
    workflow.add_node("profile", profile_node)
    workflow.add_node("detect_hotspots", detect_hotspots_node)
    workflow.add_node("generate_optimizations", generate_optimizations_node)
    
    # 定义边
    # 1. 从 START 开始代码提取
    workflow.add_edge(START, "extract_code")
    
    # 2. 代码提取后，并行执行内存分析与（可选）动态剖析
    workflow.add_edge("extract_code", "analyze_memory")

    workflow.add_edge("extract_code", "profile")
    
    # 5. 内存分析和性能剖析汇聚到热点检测
    workflow.add_edge("analyze_memory", "detect_hotspots")
    workflow.add_edge("profile", "detect_hotspots")
    
    # 6. 热点检测后生成优化建议
    workflow.add_edge("detect_hotspots", "generate_optimizations")
    
    # 7. 结束
    workflow.add_edge("generate_optimizations", END)
    
    return workflow.compile()


def run_performance_analysis(project_path: str, source_files: List[str],
                             language: str = "c",
                             enable_profiling: bool = False,
                             profiling_executable: str | None = None,
                             profiling_args: List[str] | None = None,
                             profiling_cwd: str | None = None) -> PerformanceState:
    """
    运行完整的性能分析
    
    Args:
        project_path: 项目路径
        source_files: 源文件列表
        language: 编程语言
        enable_profiling: 是否启用动态性能剖析
    
    Returns:
        完整的性能分析状态
    """
    logger.info(f"🚀 开始性能分析: {project_path}")
    logger.info(f"   语言: {language}, 文件数: {len(source_files)}, 动态剖析: {enable_profiling}")
    
    # 初始化状态
    initial_state: PerformanceState = {
        "project_path": project_path,
        "source_files": source_files,
        "language": language,
        "functions": [],
        "data_structures": [],
        "call_graph": {},
        "algorithms": [],
        "complexities": [],
        "memory_issues": [],
        "memory_patterns": "",
        "profiling_data": None,
        "profiling_enabled": enable_profiling,
        "profiling_executable": profiling_executable,
        "profiling_args": profiling_args or [],
        "profiling_cwd": profiling_cwd,
        "profiling_output": "",
        "hotspots": [],
        "optimizations": [],
        "performance_report": ""
    }
    
    # 创建并运行子图
    perf_graph = create_performance_subgraph()
    final_state = perf_graph.invoke(initial_state)
    
    logger.info("🏁 性能分析完成")
    
    return final_state


def collect_source_files(project_path: str, language: str = "c") -> List[str]:
    """收集项目中的源文件"""
    extensions = {
        "c": [".c", ".h"],
        "python": [".py"],
        "go": [".go"],
        "cpp": [".cpp", ".hpp", ".cc", ".hh"],
    }
    
    exts = extensions.get(language, [".c", ".h"])
    source_files = []
    
    for root, dirs, files in os.walk(project_path):
        # 跳过常见的非源码目录
        dirs[:] = [d for d in dirs if d not in ['build', 'node_modules', '.git', '__pycache__', 'venv']]
        
        for f in files:
            if any(f.endswith(ext) for ext in exts):
                source_files.append(os.path.join(root, f))
    
    return source_files
