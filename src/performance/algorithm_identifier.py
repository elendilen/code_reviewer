"""
Algorithm Identifier Agent - 算法识别器
负责识别代码中的算法模式、数据结构操作和设计模式
"""
import re
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .perf_state import PerformanceState, AlgorithmMatch, FunctionInfo
from ..utils.logger import setup_logger

logger = setup_logger("algorithm_identifier")


# 算法模式知识库
ALGORITHM_PATTERNS = {
    "sorting": {
        "bubble_sort": {
            "indicators": ["swap", "nested loop", "adjacent comparison"],
            "complexity": "O(n²)",
            "patterns": [r'for.*for.*swap', r'if.*\[.*\].*>.*\[.*\+.*1\]']
        },
        "quick_sort": {
            "indicators": ["pivot", "partition", "recursive"],
            "complexity": "O(n log n) average",
            "patterns": [r'pivot', r'partition', r'quicksort.*\(.*,.*\)']
        },
        "merge_sort": {
            "indicators": ["merge", "divide", "recursive", "mid"],
            "complexity": "O(n log n)",
            "patterns": [r'merge', r'mid\s*=', r'mergesort']
        },
        "heap_sort": {
            "indicators": ["heapify", "heap", "sift"],
            "complexity": "O(n log n)",
            "patterns": [r'heapify', r'sift', r'build.*heap']
        }
    },
    "searching": {
        "binary_search": {
            "indicators": ["mid", "left", "right", "sorted"],
            "complexity": "O(log n)",
            "patterns": [r'mid\s*=.*\(.*left.*\+.*right\).*/', r'while.*left.*<.*right']
        },
        "linear_search": {
            "indicators": ["sequential", "iterate all"],
            "complexity": "O(n)",
            "patterns": [r'for.*if.*==.*return']
        },
        "hash_lookup": {
            "indicators": ["hash", "bucket", "key"],
            "complexity": "O(1) average",
            "patterns": [r'hash', r'bucket', r'\[.*%.*\]']
        }
    },
    "graph": {
        "bfs": {
            "indicators": ["queue", "visited", "level", "breadth"],
            "complexity": "O(V + E)",
            "patterns": [r'queue', r'enqueue', r'dequeue', r'visited']
        },
        "dfs": {
            "indicators": ["stack", "recursive", "visited", "depth"],
            "complexity": "O(V + E)",
            "patterns": [r'dfs', r'visited.*=.*true', r'recursive.*call']
        },
        "dijkstra": {
            "indicators": ["distance", "priority queue", "shortest"],
            "complexity": "O((V + E) log V)",
            "patterns": [r'dist', r'priority', r'shortest']
        }
    },
    "cache": {
        "lru": {
            "indicators": ["least recently used", "doubly linked list", "hash map", "head", "tail"],
            "complexity": "O(1) get/put",
            "patterns": [r'lru', r'head.*tail', r'move.*to.*front']
        },
        "lfu": {
            "indicators": ["least frequently used", "frequency", "count"],
            "complexity": "O(1) with proper structure",
            "patterns": [r'lfu', r'frequency', r'freq.*count']
        },
        "fifo": {
            "indicators": ["first in first out", "queue"],
            "complexity": "O(1)",
            "patterns": [r'fifo', r'queue.*push.*pop']
        }
    },
    "dynamic_programming": {
        "memoization": {
            "indicators": ["memo", "cache", "dp table", "subproblem"],
            "complexity": "Varies",
            "patterns": [r'memo', r'dp\[', r'cache\[']
        },
        "tabulation": {
            "indicators": ["bottom up", "table", "dp array"],
            "complexity": "Varies",
            "patterns": [r'dp\[.*\]\s*=', r'for.*dp\[']
        }
    },
    "ftl_specific": {
        "wear_leveling": {
            "indicators": ["wear", "erase count", "balance", "block selection"],
            "complexity": "O(n) or O(log n)",
            "patterns": [r'wear', r'erase.*count', r'level']
        },
        "garbage_collection": {
            "indicators": ["gc", "valid pages", "victim", "reclaim"],
            "complexity": "O(n)",
            "patterns": [r'gc', r'garbage', r'victim', r'valid.*page', r'reclaim']
        },
        "address_mapping": {
            "indicators": ["mapping", "logical", "physical", "translate"],
            "complexity": "O(1) with hash, O(log n) with tree",
            "patterns": [r'map', r'translate', r'l2p', r'logical.*physical']
        }
    }
}


class AlgorithmIdentifierAgent:
    """算法识别器 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
    
    def identify(self, state: PerformanceState) -> Dict[str, Any]:
        """识别代码中的算法"""
        functions = state["functions"]
        language = state.get("language", "c")
        
        logger.info(f"开始算法识别，分析 {len(functions)} 个函数")
        
        all_algorithms: List[AlgorithmMatch] = []
        
        # 1. 基于模式匹配的快速识别
        for func in functions:
            matches = self._pattern_match(func)
            all_algorithms.extend(matches)
        
        # 2. 使用 LLM 进行深度算法识别
        if functions:
            llm_matches = self._llm_identify(functions, language)
            all_algorithms.extend(llm_matches)
        
        # 3. 去重和排序
        all_algorithms = self._deduplicate_and_rank(all_algorithms)
        
        logger.info(f"算法识别完成，发现 {len(all_algorithms)} 个算法模式")
        
        return {"algorithms": all_algorithms}
    
    def _pattern_match(self, func: FunctionInfo) -> List[AlgorithmMatch]:
        """基于模式匹配识别算法"""
        matches = []
        code = func.get("code_snippet", "").lower()
        func_name = func.get("name", "").lower()
        
        for category, algorithms in ALGORITHM_PATTERNS.items():
            for algo_name, algo_info in algorithms.items():
                confidence = 0.0
                evidence = []
                
                # 检查函数名
                if any(ind.lower() in func_name for ind in algo_info["indicators"]):
                    confidence += 0.3
                    evidence.append(f"函数名包含关键词")
                
                # 检查代码模式
                for pattern in algo_info["patterns"]:
                    if re.search(pattern, code, re.IGNORECASE):
                        confidence += 0.2
                        evidence.append(f"匹配模式: {pattern[:30]}")
                
                # 检查指示词
                indicator_count = sum(1 for ind in algo_info["indicators"] 
                                     if ind.lower() in code)
                if indicator_count > 0:
                    confidence += 0.1 * min(indicator_count, 3)
                    evidence.append(f"发现 {indicator_count} 个指示词")
                
                if confidence >= 0.3:  # 阈值
                    matches.append(AlgorithmMatch(
                        name=algo_name.replace('_', ' ').title(),
                        category=category,
                        confidence=min(confidence, 1.0),
                        location=f"{func['file']}:{func['start_line']}-{func['end_line']}",
                        evidence=evidence,
                        standard_complexity=algo_info["complexity"],
                        reference=""
                    ))
        
        return matches
    
    def _llm_identify(self, functions: List[FunctionInfo], 
                      language: str) -> List[AlgorithmMatch]:
        """使用 LLM 识别算法"""
        # 选择最可能包含算法的函数
        candidates = sorted(functions,
                           key=lambda f: len(f.get("loops", [])) * 2 + 
                                        (1 if f.get("recursion") else 0) * 3,
                           reverse=True)[:5]
        
        if not candidates:
            return []
        
        code_samples = ""
        for func in candidates:
            code_samples += f"\n### 函数: {func['name']}\n"
            code_samples += f"位置: {func['file']}:{func['start_line']}-{func['end_line']}\n"
            code_samples += f"循环数: {len(func.get('loops', []))}, 递归: {func.get('recursion', False)}\n"
            code_samples += f"```{language}\n{func.get('code_snippet', '')[:1000]}\n```\n"
        
        prompt = f"""
你是一个算法专家。分析以下代码，识别其中使用的算法和数据结构模式。

{code_samples}

请识别：
1. 排序算法（冒泡、快排、归并、堆排序等）
2. 搜索算法（线性、二分、哈希等）
3. 图算法（BFS、DFS、Dijkstra等）
4. 动态规划
5. 缓存策略（LRU、LFU、FIFO等）
6. FTL相关（垃圾回收、磨损均衡、地址映射）
7. 其他经典算法

对于每个识别到的算法，给出：
- 算法名称
- 所属类别
- 置信度(0-1)
- 位置（函数名）
- 识别依据
- 标准复杂度

输出 JSON 格式：
[
  {{
    "name": "算法名称",
    "category": "类别",
    "confidence": 0.85,
    "function": "函数名",
    "evidence": ["依据1", "依据2"],
    "complexity": "O(...)"
  }}
]

如果没有识别到明确的算法，返回空数组 []
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            
            # 解析 JSON
            import json
            # 提取 JSON 部分
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                algorithms_data = json.loads(json_match.group())
                
                matches = []
                for algo in algorithms_data:
                    # 找到对应的函数位置
                    func_name = algo.get("function", "")
                    location = func_name
                    for f in candidates:
                        if f["name"] == func_name:
                            location = f"{f['file']}:{f['start_line']}-{f['end_line']}"
                            break
                    
                    matches.append(AlgorithmMatch(
                        name=algo.get("name", "Unknown"),
                        category=algo.get("category", "other"),
                        confidence=float(algo.get("confidence", 0.5)),
                        location=location,
                        evidence=algo.get("evidence", []),
                        standard_complexity=algo.get("complexity", "Unknown"),
                        reference=""
                    ))
                
                logger.info(f"LLM 识别到 {len(matches)} 个算法")
                return matches
                
        except Exception as e:
            logger.warning(f"LLM 算法识别失败: {e}")
        
        return []
    
    def _deduplicate_and_rank(self, algorithms: List[AlgorithmMatch]) -> List[AlgorithmMatch]:
        """去重并按置信度排序"""
        # 按 (name, location) 去重，保留置信度最高的
        seen = {}
        for algo in algorithms:
            key = (algo["name"].lower(), algo["location"])
            if key not in seen or algo["confidence"] > seen[key]["confidence"]:
                seen[key] = algo
        
        # 按置信度排序
        result = sorted(seen.values(), key=lambda x: x["confidence"], reverse=True)
        return result
