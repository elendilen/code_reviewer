"""
Hotspot Detector Agent - 热点检测器
结合静态分析和动态数据定位性能热点
"""
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .perf_state import (PerformanceState, HotspotInfo, FunctionInfo, 
                         ProfilingData)
from ..utils.logger import setup_logger

logger = setup_logger("hotspot_detector")


class HotspotDetectorAgent:
    """热点检测器 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
    
    def detect(self, state: PerformanceState) -> Dict[str, Any]:
        """检测性能热点"""
        functions = state["functions"]
        profiling_data = state.get("profiling_data")
        memory_issues = state.get("memory_issues", [])
        
        logger.info(f"开始热点检测，分析 {len(functions)} 个函数")
        
        # 1. 基于静态分析评分
        static_scores = self._static_hotspot_scoring(functions, memory_issues)
        
        # 2. 如果有 profiling 数据，结合动态数据
        if profiling_data and profiling_data.get("hotspots"):
            dynamic_scores = self._dynamic_hotspot_scoring(profiling_data)
            scores = self._merge_scores(static_scores, dynamic_scores)
        else:
            scores = static_scores
        
        # 3. 使用 LLM 综合分析
        hotspots = self._llm_hotspot_analysis(functions, memory_issues, scores)
        
        # 4. 排序和筛选
        hotspots = sorted(hotspots, key=lambda x: x.get("rank", 999))[:10]
        
        logger.info(f"热点检测完成，发现 {len(hotspots)} 个热点")
        
        return {"hotspots": hotspots}
    
    def _static_hotspot_scoring(self, functions: List[FunctionInfo],
                                memory_issues: List) -> Dict[str, float]:
        """基于静态分析的热点评分"""
        scores = {}
        
        for func in functions:
            score = 0.0
            func_name = func["name"]
            
            # 1. 循环数量和嵌套深度
            loops = func.get("loops", [])
            loop_score = len(loops) * 0.2
            score += min(loop_score, 1.0)
            
            # 2. 递归
            if func.get("recursion"):
                score += 0.3
            
            # 3. 调用其他函数的数量
            calls = func.get("calls", [])
            if len(calls) > 5:
                score += 0.2
            
            # 4. 函数大小
            code_len = len(func.get("code_snippet", ""))
            if code_len > 1000:
                score += 0.2

            # 5. 若同文件存在高严重性内存问题，稍微提高该文件函数的优先级
            func_file = func.get("file", "")
            if func_file:
                high_mem_issues_in_file = any(
                    (i.get("severity") == "high") and (i.get("file") == func_file)
                    for i in (memory_issues or [])
                )
                if high_mem_issues_in_file:
                    score += 0.15
            
            scores[func_name] = score
        
        return scores
    
    def _dynamic_hotspot_scoring(self, profiling_data: ProfilingData) -> Dict[str, float]:
        """基于动态分析的热点评分"""
        scores = {}
        
        hotspots = profiling_data.get("hotspots", [])
        for spot in hotspots:
            func_name = spot.get("function", "")
            percent = float(spot.get("percent", "0").replace("%", ""))
            scores[func_name] = percent / 100.0 * 2  # 归一化到 0-2 范围
        
        return scores
    
    def _merge_scores(self, static: Dict[str, float], 
                      dynamic: Dict[str, float]) -> Dict[str, float]:
        """合并静态和动态评分"""
        merged = {}
        all_funcs = set(static.keys()) | set(dynamic.keys())
        
        for func in all_funcs:
            # 动态数据权重更高
            s_score = static.get(func, 0)
            d_score = dynamic.get(func, 0)
            merged[func] = s_score * 0.4 + d_score * 0.6
        
        return merged
    
    def _llm_hotspot_analysis(self, functions: List[FunctionInfo],
                              memory_issues: List,
                              scores: Dict[str, float]) -> List[HotspotInfo]:
        """使用 LLM 综合分析热点"""
        # 选择评分最高的函数
        top_funcs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if not top_funcs:
            return []
        
        # 准备分析数据
        analysis_data = ""
        for func_name, score in top_funcs:
            func_info = next((f for f in functions if f["name"] == func_name), None)
            
            if func_info:
                analysis_data += f"\n### {func_name} (评分: {score:.2f})\n"
                analysis_data += f"位置: {func_info['file']}:{func_info['start_line']}-{func_info['end_line']}\n"
                analysis_data += (
                    f"循环: {len(func_info.get('loops', []))}, "
                    f"递归: {func_info.get('recursion', False)}, "
                    f"调用数: {len(func_info.get('calls', []))}\n"
                )
                
                analysis_data += f"代码:\n```\n{func_info.get('code_snippet', '')[:800]}\n```\n"
        
        # 内存问题信息
        if memory_issues:
            analysis_data += "\n### 内存问题\n"
            for issue in memory_issues[:5]:
                analysis_data += f"- {issue['type']}: {issue['description']} ({issue['file']}:{issue['line']})\n"
        
        prompt = f"""
你是一个性能优化专家。基于以下分析数据，确定代码中的性能热点。

{analysis_data}

请为每个热点提供：
1. 严重程度（CRITICAL/HIGH/MEDIUM/LOW）
2. 根本原因分析
3. 具体的代码位置

输出 JSON 格式：
[
  {{
    "rank": 1,
    "function": "函数名",
    "severity": "CRITICAL/HIGH/MEDIUM/LOW",
    "root_cause": "详细的根本原因分析",
    "static_analysis": {{
      "complexity": "O(...)",
      "call_frequency": "高/中/低"
    }}
  }}
]
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            
            import json
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                hotspots_data = json.loads(json_match.group())
                
                hotspots = []
                for i, spot in enumerate(hotspots_data):
                    func_name = spot.get("function", "")
                    func_info = next((f for f in functions if f["name"] == func_name), None)
                    
                    if func_info:
                        hotspots.append(HotspotInfo(
                            rank=spot.get("rank", i + 1),
                            function=func_name,
                            file=func_info["file"],
                            lines=f"{func_info['start_line']}-{func_info['end_line']}",
                            severity=spot.get("severity", "MEDIUM"),
                            static_analysis=spot.get("static_analysis", {}),
                            dynamic_data=None,
                            root_cause=spot.get("root_cause", "")
                        ))
                
                return hotspots
                
        except Exception as e:
            logger.warning(f"LLM 热点分析失败: {e}")
        
        # 回退到基于评分的简单结果
        hotspots = []
        for i, (func_name, score) in enumerate(top_funcs):
            func_info = next((f for f in functions if f["name"] == func_name), None)
            if func_info:
                severity = "HIGH" if score > 1.5 else "MEDIUM" if score > 0.8 else "LOW"
                hotspots.append(HotspotInfo(
                    rank=i + 1,
                    function=func_name,
                    file=func_info["file"],
                    lines=f"{func_info['start_line']}-{func_info['end_line']}",
                    severity=severity,
                    static_analysis={"score": score},
                    dynamic_data=None,
                    root_cause=f"评分 {score:.2f}（基于循环/递归/调用/规模等静态分析）"
                ))
        
        return hotspots
