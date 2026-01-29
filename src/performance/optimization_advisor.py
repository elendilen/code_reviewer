"""
Optimization Advisor Agent - 优化顾问
汇总所有分析结果，给出具体可行的优化方案
"""
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .perf_state import (PerformanceState, OptimizationSuggestion, HotspotInfo,
                         MemoryIssue)
from ..utils.logger import setup_logger

logger = setup_logger("optimization_advisor")


# 优化模式知识库
OPTIMIZATION_PATTERNS = {
    "algorithm_replacement": {
        "linear_to_binary": {
            "problem": "线性搜索 O(n)",
            "solution": "使用二分搜索 O(log n)（需要数据有序）",
            "condition": "数据已排序或可以排序"
        },
        "bubble_to_quick": {
            "problem": "冒泡排序 O(n²)",
            "solution": "使用快速排序 O(n log n)",
            "condition": "通用场景"
        },
        "list_to_hashmap": {
            "problem": "链表查找 O(n)",
            "solution": "使用哈希表 O(1)",
            "condition": "需要频繁查找"
        },
        "array_to_heap": {
            "problem": "数组找最值 O(n)",
            "solution": "使用堆 O(log n)",
            "condition": "频繁获取最大/最小值"
        }
    },
    "loop_optimization": {
        "loop_unrolling": {
            "problem": "循环开销大",
            "solution": "循环展开",
            "code_example": "// 展开前\nfor(i=0;i<n;i++) a[i]=0;\n// 展开后\nfor(i=0;i<n;i+=4) {a[i]=0;a[i+1]=0;a[i+2]=0;a[i+3]=0;}"
        },
        "loop_fusion": {
            "problem": "多个循环遍历同一数组",
            "solution": "合并循环",
        },
        "loop_invariant": {
            "problem": "循环内重复计算",
            "solution": "将不变量移到循环外",
        }
    },
    "memory_optimization": {
        "object_pool": {
            "problem": "频繁分配/释放小对象",
            "solution": "使用对象池",
        },
        "preallocate": {
            "problem": "动态增长的数组",
            "solution": "预分配足够空间",
        },
        "cache_friendly": {
            "problem": "缓存不友好的访问模式",
            "solution": "改为连续内存访问",
        }
    },
    "parallelization": {
        "parallel_loop": {
            "problem": "可并行的独立循环",
            "solution": "使用 OpenMP 或线程池并行化",
        },
        "async_io": {
            "problem": "同步 I/O 阻塞",
            "solution": "使用异步 I/O",
        }
    }
}


class OptimizationAdvisorAgent:
    """优化顾问 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)
    
    def advise(self, state: PerformanceState) -> Dict[str, Any]:
        """生成优化建议"""
        functions = state["functions"]
        hotspots = state.get("hotspots", [])
        memory_issues = state.get("memory_issues", [])
        language = state.get("language", "c")
        
        logger.info(f"开始生成优化建议，{len(hotspots)} 个热点")
        
        optimizations: List[OptimizationSuggestion] = []
        
        # 1. 基于热点生成优化建议
        for hotspot in hotspots[:5]:
            suggestions = self._generate_hotspot_suggestions(
                hotspot, functions, language
            )
            optimizations.extend(suggestions)
        
        # 2. 基于内存问题生成优化建议
        memory_suggestions = self._generate_memory_suggestions(memory_issues, language)
        optimizations.extend(memory_suggestions)
        
        # 3. 使用 LLM 生成综合优化报告
        if hotspots:
            llm_suggestions = self._llm_optimization_analysis(
                state, functions, hotspots, memory_issues, language
            )
            optimizations.extend(llm_suggestions)
        
        # 4. 去重和排序
        optimizations = self._deduplicate_and_prioritize(optimizations)
        
        # 5. 生成性能报告
        performance_report = self._generate_performance_report(
            state, optimizations
        )
        
        logger.info(f"生成了 {len(optimizations)} 条优化建议")
        
        return {
            "optimizations": optimizations,
            "performance_report": performance_report
        }
    
    def _generate_hotspot_suggestions(self, hotspot: HotspotInfo,
                                       functions: List,
                                       language: str) -> List[OptimizationSuggestion]:
        """为热点生成优化建议"""
        suggestions = []
        func_name = hotspot["function"]
        
        # 找到对应的函数信息
        func_info = next((f for f in functions if f["name"] == func_name), None)
        
        if not func_info:
            return suggestions
        
        # 检查循环优化机会
        loops = func_info.get("loops", [])
        if len(loops) >= 2:
            suggestions.append(OptimizationSuggestion(
                target=func_name,
                priority="medium",
                category="loop",
                problem=f"函数包含 {len(loops)} 个循环，可能存在优化空间",
                solution="检查是否可以合并循环（loop fusion）或将循环不变量移出循环",
                code_before="",
                code_after="",
                expected_improvement="减少循环开销和内存访问"
            ))

        # 高调用扇出：考虑缓存/批处理/减少跨层调用
        calls = func_info.get("calls", [])
        if len(calls) >= 8:
            suggestions.append(OptimizationSuggestion(
                target=func_name,
                priority="medium",
                category="cache",
                problem=f"函数调用其他函数较多（{len(calls)} 个），可能存在频繁小调用开销/重复计算",
                solution="检查是否存在可缓存的中间结果；将细粒度调用合并为批处理；减少重复的边界检查与日志",
                code_before="",
                code_after="",
                expected_improvement="减少函数调用开销与重复计算"
            ))
        
        return suggestions
    
    def _generate_memory_suggestions(self, memory_issues: List[MemoryIssue],
                                      language: str) -> List[OptimizationSuggestion]:
        """基于内存问题生成建议"""
        suggestions = []
        
        for issue in memory_issues[:5]:
            if issue["type"] == "potential_leak":
                suggestions.append(OptimizationSuggestion(
                    target=f"{issue['file']}:{issue['line']}",
                    priority="high",
                    category="memory",
                    problem=issue["description"],
                    solution=issue["suggestion"],
                    code_before="",
                    code_after="",
                    expected_improvement="消除内存泄漏"
                ))
            elif issue["type"] == "missing_null_check":
                suggestions.append(OptimizationSuggestion(
                    target=f"{issue['file']}:{issue['line']}",
                    priority="medium",
                    category="memory",
                    problem=issue["description"],
                    solution=issue["suggestion"],
                    code_before="ptr = malloc(size);\nuse(ptr);",
                    code_after="ptr = malloc(size);\nif(ptr == NULL) { /* handle error */ }\nuse(ptr);",
                    expected_improvement="提高代码健壮性"
                ))
        
        return suggestions
    
    def _llm_optimization_analysis(self, state: PerformanceState,
                                   functions: List,
                                   hotspots: List[HotspotInfo],
                                   memory_issues: List,
                                   language: str) -> List[OptimizationSuggestion]:
        """使用 LLM 生成详细优化建议"""
        # 准备上下文
        context = "## 热点函数分析\n\n"
        
        for hotspot in hotspots[:3]:
            func_name = hotspot["function"]
            func_info = next((f for f in functions if f["name"] == func_name), None)
            
            if func_info:
                context += f"### {func_name} [{hotspot['severity']}]\n"
                context += f"位置: {hotspot['file']}:{hotspot['lines']}\n"
                context += f"根本原因: {hotspot['root_cause']}\n"
                context += f"```{language}\n{func_info.get('code_snippet', '')[:1000]}\n```\n\n"

        profiling_data = state.get("profiling_data")
        if profiling_data and profiling_data.get("hotspots"):
            context += "## 动态剖析摘要\n\n"
            context += f"- 总耗时: {profiling_data.get('total_time', 'N/A')}\n"
            for spot in profiling_data.get("hotspots", [])[:5]:
                context += f"- {spot.get('function', '')}: {spot.get('percent', '')}\n"
            context += "\n"
        
        prompt = f"""
你是一个高级性能优化专家。基于以下分析结果，为每个热点函数提供具体的优化方案。

{context}

对于每个热点，请提供：
1. 具体的优化方案（不是泛泛的建议）
2. 优化前的代码示例
3. 优化后的代码示例
4. 预期的性能提升

注意：不要输出“算法名称/时间复杂度推导”。只关注可落地的性能优化（减少 CPU 指令数、减少内存访问/分配、改进 I/O、并行化、缓存等）。

输出 JSON 格式：
[
  {{
    "target": "函数名",
    "priority": "high/medium/low",
    "category": "algorithm/data_structure/memory/parallelization/cache",
    "problem": "问题描述",
    "solution": "详细的解决方案",
    "code_before": "优化前代码",
    "code_after": "优化后代码",
    "expected_improvement": "预期提升"
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
                suggestions_data = json.loads(json_match.group())
                
                suggestions = []
                for s in suggestions_data:
                    suggestions.append(OptimizationSuggestion(
                        target=s.get("target", ""),
                        priority=s.get("priority", "medium"),
                        category=s.get("category", "other"),
                        problem=s.get("problem", ""),
                        solution=s.get("solution", ""),
                        code_before=s.get("code_before", ""),
                        code_after=s.get("code_after", ""),
                        expected_improvement=s.get("expected_improvement", "")
                    ))
                
                return suggestions
                
        except Exception as e:
            logger.warning(f"LLM 优化分析失败: {e}")
        
        return []
    
    def _deduplicate_and_prioritize(self, 
                                     suggestions: List[OptimizationSuggestion]) -> List[OptimizationSuggestion]:
        """去重并按优先级排序"""
        seen = set()
        unique = []
        
        for s in suggestions:
            key = (s["target"], s["category"])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        unique.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        return unique
    
    def _generate_performance_report(self, state: PerformanceState,
                                      optimizations: List[OptimizationSuggestion]) -> str:
        """生成完整的性能分析报告"""
        report = "# 性能分析报告\n\n"
        
        # 项目概览
        report += "## 1. 项目概览\n\n"
        report += f"- 项目路径: `{state['project_path']}`\n"
        report += f"- 语言: {state.get('language', 'C')}\n"
        report += f"- 分析函数数: {len(state.get('functions', []))}\n"
        report += f"- 动态剖析: {'启用' if state.get('profiling_enabled') else '未启用'}\n\n"

        # 动态剖析摘要
        profiling_data = state.get("profiling_data")
        if profiling_data:
            report += "## 2. 动态剖析解读\n\n"
            report += f"- 总耗时: {profiling_data.get('total_time', 'N/A')}\n"
            report += f"- 内存峰值: {profiling_data.get('memory_peak', 'N/A')}\n"

            cache_info = profiling_data.get("cache_info") or {}
            if cache_info:
                # 只挑关键指标展示
                if cache_info.get("cpu_percent"):
                    report += f"- CPU 使用率: {cache_info.get('cpu_percent')}\n"
                if cache_info.get("user_time_s") or cache_info.get("system_time_s"):
                    report += (
                        f"- CPU 时间: user={cache_info.get('user_time_s', 'N/A')}s, "
                        f"sys={cache_info.get('system_time_s', 'N/A')}s\n"
                    )
                if cache_info.get("major_page_faults") or cache_info.get("minor_page_faults"):
                    report += (
                        f"- 页错误: major={cache_info.get('major_page_faults', 'N/A')}, "
                        f"minor={cache_info.get('minor_page_faults', 'N/A')}\n"
                    )
                if cache_info.get("voluntary_ctx_switches") or cache_info.get("involuntary_ctx_switches"):
                    report += (
                        f"- 上下文切换: voluntary={cache_info.get('voluntary_ctx_switches', 'N/A')}, "
                        f"involuntary={cache_info.get('involuntary_ctx_switches', 'N/A')}\n"
                    )
                if cache_info.get("fs_inputs") or cache_info.get("fs_outputs"):
                    report += (
                        f"- 文件系统 I/O: in={cache_info.get('fs_inputs', 'N/A')}, "
                        f"out={cache_info.get('fs_outputs', 'N/A')}\n"
                    )

            # 简单结论（不展示原始输出）
            cpu_percent = (cache_info.get("cpu_percent") or "").strip()
            if cpu_percent.endswith("%"):
                try:
                    cpu_val = int(cpu_percent[:-1])
                    if cpu_val >= 90:
                        report += "\n**初步判断**: CPU 绑定较明显，优先关注热点函数与算法/数据结构层面的优化。\n\n"
                    elif cpu_val <= 40:
                        report += "\n**初步判断**: 可能存在 I/O 绑定或等待（CPU 利用率偏低），优先检查磁盘访问/系统调用/锁等待。\n\n"
                except Exception:
                    pass
        
        # 性能热点
        hotspots = state.get("hotspots", [])
        if hotspots:
            report += "## 3. 性能热点\n\n"
            for spot in hotspots[:5]:
                report += f"### 🔥 #{spot['rank']} {spot['function']} [{spot['severity']}]\n\n"
                report += f"- **位置**: `{spot['file']}:{spot['lines']}`\n"
                report += f"- **根本原因**: {spot['root_cause']}\n\n"
        
        # 内存问题
        memory_issues = state.get("memory_issues", [])
        if memory_issues:
            report += "## 4. 内存问题\n\n"
            high_issues = [i for i in memory_issues if i['severity'] == 'high']
            if high_issues:
                report += f"⚠️ 发现 **{len(high_issues)}** 个高严重性内存问题\n\n"
            for issue in memory_issues[:5]:
                icon = "🔴" if issue['severity'] == 'high' else "🟡" if issue['severity'] == 'medium' else "🟢"
                report += f"{icon} **{issue['type']}** ({issue['file']}:{issue['line']})\n"
                report += f"   {issue['description']}\n\n"
        
        # 优化建议
        if optimizations:
            report += "## 5. 优化建议\n\n"
            for i, opt in enumerate(optimizations[:10], 1):
                priority_icon = "🔴" if opt['priority'] == 'high' else "🟡" if opt['priority'] == 'medium' else "🟢"
                report += f"### {priority_icon} 建议 {i}: {opt['target']}\n\n"
                report += f"**类别**: {opt['category']} | **优先级**: {opt['priority']}\n\n"
                report += f"**问题**: {opt['problem']}\n\n"
                report += f"**解决方案**: {opt['solution']}\n\n"
                
                if opt.get('code_before') and opt.get('code_after'):
                    report += "**代码示例**:\n\n"
                    report += f"优化前:\n```c\n{opt['code_before']}\n```\n\n"
                    report += f"优化后:\n```c\n{opt['code_after']}\n```\n\n"
                
                report += f"**预期提升**: {opt['expected_improvement']}\n\n"
                report += "---\n\n"
        
        # 总结
        report += "## 6. 总结\n\n"
        high_priority = len([o for o in optimizations if o['priority'] == 'high'])
        report += f"- 发现 **{len(hotspots)}** 个性能热点\n"
        report += f"- 发现 **{len(memory_issues)}** 个内存问题\n"
        report += f"- 生成 **{len(optimizations)}** 条优化建议\n"
        report += f"- 其中 **{high_priority}** 条为高优先级\n"
        
        return report
