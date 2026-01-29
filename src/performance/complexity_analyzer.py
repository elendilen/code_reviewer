"""
Complexity Analyzer Agent - 复杂度分析器
负责推导函数的时间和空间复杂度
"""
import re
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .perf_state import PerformanceState, ComplexityResult, FunctionInfo, AlgorithmMatch
from ..utils.logger import setup_logger

logger = setup_logger("complexity_analyzer")


class ComplexityAnalyzerAgent:
    """复杂度分析器 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
    
    def analyze(self, state: PerformanceState) -> Dict[str, Any]:
        """分析函数复杂度"""
        functions = state["functions"]
        algorithms = state.get("algorithms", [])
        language = state.get("language", "c")
        
        logger.info(f"开始复杂度分析，分析 {len(functions)} 个函数")
        
        complexities: List[ComplexityResult] = []
        
        # 1. 对每个函数进行静态分析
        for func in functions:
            # 先尝试静态分析
            static_result = self._static_analyze(func)
            
            # 检查是否有已识别的算法可以参考
            algo_complexity = self._get_algorithm_complexity(func, algorithms)
            
            if algo_complexity:
                static_result["time_complexity"]["reference"] = algo_complexity
            
            complexities.append(static_result)
        
        # 2. 使用 LLM 进行深度分析
        if functions:
            complexities = self._llm_analyze(functions, complexities, language)
        
        logger.info(f"复杂度分析完成，分析了 {len(complexities)} 个函数")
        
        return {"complexities": complexities}
    
    def _static_analyze(self, func: FunctionInfo) -> ComplexityResult:
        """静态分析复杂度"""
        loops = func.get("loops", [])
        recursion = func.get("recursion", False)
        code = func.get("code_snippet", "")
        
        # 计算循环嵌套深度
        loop_depth = self._calculate_loop_depth(code)
        
        # 基于循环深度估计时间复杂度
        if loop_depth == 0 and not recursion:
            time_complexity = "O(1)"
        elif loop_depth == 1:
            time_complexity = "O(n)"
        elif loop_depth == 2:
            time_complexity = "O(n²)"
        elif loop_depth == 3:
            time_complexity = "O(n³)"
        else:
            time_complexity = f"O(n^{loop_depth})"
        
        # 检查是否有特殊模式
        if recursion:
            # 检查是否是分治
            if "mid" in code.lower() or "/2" in code or ">>1" in code:
                time_complexity = "O(n log n) 或 O(log n)"
            else:
                time_complexity = "O(2^n) 或 O(n!)"  # 最坏情况假设
        
        # 检查是否有二分特征
        if self._has_binary_search_pattern(code):
            time_complexity = "O(log n)"
        
        # 空间复杂度估计
        space_complexity = self._estimate_space_complexity(func)
        
        # 识别瓶颈
        bottleneck = self._identify_bottleneck(func, loops)
        
        return ComplexityResult(
            function=func["name"],
            file=func["file"],
            time_complexity={
                "best": time_complexity,
                "average": time_complexity,
                "worst": time_complexity
            },
            space_complexity={
                "auxiliary": space_complexity,
                "total": space_complexity
            },
            derivation=[
                f"循环嵌套深度: {loop_depth}",
                f"递归: {'是' if recursion else '否'}",
                f"循环数量: {len(loops)}"
            ],
            bottleneck=bottleneck
        )
    
    def _calculate_loop_depth(self, code: str) -> int:
        """计算循环嵌套深度"""
        max_depth = 0
        current_depth = 0
        
        # 简单的基于关键词的深度计算
        lines = code.split('\n')
        for line in lines:
            stripped = line.strip()
            if re.match(r'(for|while)\s*\(', stripped):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif stripped == '}':
                current_depth = max(0, current_depth - 1)
        
        return max_depth
    
    def _has_binary_search_pattern(self, code: str) -> bool:
        """检查是否有二分查找模式"""
        patterns = [
            r'mid\s*=.*\(.*\+.*\).*[/2]',
            r'left.*<.*right',
            r'low.*<.*high',
            r'>>.*1',  # 位移除2
        ]
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False
    
    def _estimate_space_complexity(self, func: FunctionInfo) -> str:
        """估计空间复杂度"""
        code = func.get("code_snippet", "")
        
        # 检查动态内存分配
        if re.search(r'malloc|calloc|new\s+\w+\[', code):
            # 检查是否是 O(n) 级别的分配
            if re.search(r'malloc\s*\(\s*\w+\s*\*', code):
                return "O(n)"
            return "O(1) 或 O(n)"
        
        # 检查递归
        if func.get("recursion"):
            return "O(n) (递归栈)"
        
        # 检查大数组
        if re.search(r'\w+\s+\w+\s*\[\s*\d{3,}\s*\]', code):
            return "O(n)"
        
        return "O(1)"
    
    def _identify_bottleneck(self, func: FunctionInfo, loops: List[Dict]) -> str:
        """识别性能瓶颈"""
        if not loops:
            return "无明显瓶颈"
        
        # 找最内层循环
        deepest_loop = max(loops, key=lambda l: l.get("line", 0), default=None)
        if deepest_loop:
            return f"最内层循环 (第 {deepest_loop.get('line', '?')} 行)"
        
        return "循环结构"
    
    def _get_algorithm_complexity(self, func: FunctionInfo, 
                                   algorithms: List[AlgorithmMatch]) -> str:
        """从已识别的算法获取复杂度"""
        func_loc = f"{func['file']}:{func['start_line']}"
        
        for algo in algorithms:
            if func_loc in algo.get("location", ""):
                return algo.get("standard_complexity", "")
        
        return ""
    
    def _llm_analyze(self, functions: List[FunctionInfo],
                     static_results: List[ComplexityResult],
                     language: str) -> List[ComplexityResult]:
        """使用 LLM 深度分析复杂度"""
        # 选择复杂度可能不准确的函数
        candidates = []
        for i, func in enumerate(functions):
            if func.get("recursion") or len(func.get("loops", [])) > 1:
                candidates.append((i, func, static_results[i]))
        
        if not candidates:
            return static_results
        
        # 只分析前 3 个最复杂的
        candidates = candidates[:3]
        
        analysis_text = ""
        for idx, func, static in candidates:
            analysis_text += f"\n### 函数 {idx + 1}: {func['name']}\n"
            analysis_text += f"位置: {func['file']}:{func['start_line']}-{func['end_line']}\n"
            analysis_text += f"静态分析结果: 时间 {static['time_complexity']['average']}, 空间 {static['space_complexity']['auxiliary']}\n"
            analysis_text += f"```{language}\n{func.get('code_snippet', '')[:1200]}\n```\n"
        
        prompt = f"""
你是一个算法复杂度分析专家。请精确分析以下函数的时间和空间复杂度。

{analysis_text}

对于每个函数，请提供：
1. 时间复杂度（最好、平均、最坏情况）
2. 空间复杂度（辅助空间、总空间）
3. 详细的推导过程
4. 性能瓶颈位置

输出 JSON 格式：
[
  {{
    "function_index": 0,
    "time_complexity": {{
      "best": "O(...)",
      "average": "O(...)",
      "worst": "O(...)"
    }},
    "space_complexity": {{
      "auxiliary": "O(...)",
      "total": "O(...)"
    }},
    "derivation": ["推导步骤1", "推导步骤2"],
    "bottleneck": "瓶颈描述"
  }}
]
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            
            import json
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                llm_results = json.loads(json_match.group())
                
                # 更新静态结果
                for result in llm_results:
                    idx = result.get("function_index", 0)
                    if idx < len(candidates):
                        original_idx = candidates[idx][0]
                        static_results[original_idx] = ComplexityResult(
                            function=static_results[original_idx]["function"],
                            file=static_results[original_idx]["file"],
                            time_complexity=result.get("time_complexity", 
                                                       static_results[original_idx]["time_complexity"]),
                            space_complexity=result.get("space_complexity",
                                                        static_results[original_idx]["space_complexity"]),
                            derivation=result.get("derivation", []),
                            bottleneck=result.get("bottleneck", "")
                        )
                
                logger.info(f"LLM 复杂度分析更新了 {len(llm_results)} 个函数")
                
        except Exception as e:
            logger.warning(f"LLM 复杂度分析失败: {e}")
        
        return static_results
