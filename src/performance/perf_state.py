"""
性能分析状态定义
"""
from typing import TypedDict, List, Dict, Any, Optional
import operator
from typing import Annotated


class FunctionInfo(TypedDict):
    """函数信息"""
    name: str
    file: str
    start_line: int
    end_line: int
    params: List[str]
    return_type: str
    calls: List[str]  # 调用的其他函数
    loops: List[Dict[str, Any]]  # 循环信息
    recursion: bool
    code_snippet: str


class DataStructureInfo(TypedDict):
    """数据结构信息"""
    name: str
    type: str  # array, linked_list, hash_table, tree, etc.
    file: str
    line: int
    size: str  # static, dynamic, unknown
    operations: List[str]


class AlgorithmMatch(TypedDict):
    """算法匹配结果"""
    name: str
    category: str  # sorting, searching, graph, dp, etc.
    confidence: float
    location: str
    evidence: List[str]
    standard_complexity: str
    reference: str


class ComplexityResult(TypedDict):
    """复杂度分析结果"""
    function: str
    file: str
    time_complexity: Dict[str, str]  # best, average, worst
    space_complexity: Dict[str, str]  # auxiliary, total
    derivation: List[str]
    bottleneck: str


class MemoryIssue(TypedDict):
    """内存问题"""
    type: str  # leak, double_free, uninitialized, buffer_overflow
    severity: str  # high, medium, low
    file: str
    line: int
    description: str
    suggestion: str


class ProfilingData(TypedDict):
    """性能剖析数据"""
    total_time: str
    hotspots: List[Dict[str, Any]]
    memory_peak: str
    cache_info: Dict[str, Any]


class HotspotInfo(TypedDict):
    """热点信息"""
    rank: int
    function: str
    file: str
    lines: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    static_analysis: Dict[str, Any]
    dynamic_data: Optional[Dict[str, Any]]
    root_cause: str


class OptimizationSuggestion(TypedDict):
    """优化建议"""
    target: str  # 优化目标函数/模块
    priority: str  # high, medium, low
    category: str  # algorithm, data_structure, memory, parallelization, cache
    problem: str
    solution: str
    code_before: str
    code_after: str
    expected_improvement: str


class PerformanceState(TypedDict):
    """性能分析子图状态"""
    project_path: str
    source_files: List[str]
    language: str
    
    # Code Extractor 输出
    functions: List[FunctionInfo]
    data_structures: List[DataStructureInfo]
    call_graph: Dict[str, List[str]]
    
    # Algorithm Identifier 输出
    algorithms: List[AlgorithmMatch]
    
    # Complexity Analyzer 输出
    complexities: List[ComplexityResult]
    
    # Memory Analyzer 输出
    memory_issues: List[MemoryIssue]
    memory_patterns: str
    
    # Profiler 输出
    profiling_data: Optional[ProfilingData]
    profiling_enabled: bool

    # Profiler 原始输出（用于终端实时展示与最终报告归档）
    profiling_output: str

    # Profiling 运行配置（可选，由 CLI 传入）
    profiling_executable: Optional[str]
    profiling_args: List[str]
    profiling_cwd: Optional[str]
    
    # Hotspot Detector 输出
    hotspots: List[HotspotInfo]
    
    # Optimization Advisor 输出
    optimizations: List[OptimizationSuggestion]
    
    # 最终报告
    performance_report: str
