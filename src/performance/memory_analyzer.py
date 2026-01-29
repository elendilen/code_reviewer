"""
Memory Analyzer Agent - 内存分析器
负责分析内存使用模式、检测潜在的内存问题
"""
import re
from typing import List, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .perf_state import PerformanceState, MemoryIssue, FunctionInfo
from ..utils.logger import setup_logger

logger = setup_logger("memory_analyzer")


class MemoryAnalyzerAgent:
    """内存分析器 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
        
        # 内存相关的模式
        self.memory_patterns = {
            'c': {
                'alloc': [
                    r'(\w+)\s*=\s*\(?\w*\s*\*?\)?\s*malloc\s*\(',
                    r'(\w+)\s*=\s*\(?\w*\s*\*?\)?\s*calloc\s*\(',
                    r'(\w+)\s*=\s*\(?\w*\s*\*?\)?\s*realloc\s*\(',
                ],
                'free': r'free\s*\(\s*(\w+)\s*\)',
                'null_check': r'if\s*\(\s*(\w+)\s*==\s*NULL',
                'array_access': r'\[\s*(\w+)\s*\]',
            },
            'python': {
                'large_list': r'(\w+)\s*=\s*\[.*\]\s*\*\s*\d+',
                'append_loop': r'\.append\s*\(',
            },
            'go': {
                'make': r'make\s*\(\s*(map|slice|chan)',
                'new': r'new\s*\(\s*\w+\s*\)',
            }
        }
    
    def analyze(self, state: PerformanceState) -> Dict[str, Any]:
        """分析内存使用"""
        functions = state["functions"]
        language = state.get("language", "c")
        
        logger.info(f"开始内存分析，语言: {language}")
        
        all_issues: List[MemoryIssue] = []
        
        # 1. 静态模式匹配检测
        for func in functions:
            issues = self._static_memory_check(func, language)
            all_issues.extend(issues)
        
        # 2. 跨函数的 alloc/free 配对检查
        if language == 'c':
            pair_issues = self._check_alloc_free_pairs(functions)
            all_issues.extend(pair_issues)
        
        # 3. 使用 LLM 进行深度分析
        if functions:
            llm_issues, memory_patterns = self._llm_memory_analyze(functions, language)
            all_issues.extend(llm_issues)
        else:
            memory_patterns = ""
        
        # 去重
        all_issues = self._deduplicate_issues(all_issues)
        
        logger.info(f"内存分析完成，发现 {len(all_issues)} 个问题")
        
        return {
            "memory_issues": all_issues,
            "memory_patterns": memory_patterns
        }
    
    def _static_memory_check(self, func: FunctionInfo, language: str) -> List[MemoryIssue]:
        """静态内存检查"""
        issues = []
        code = func.get("code_snippet", "")
        file_path = func["file"]
        
        if language == 'c':
            # 检查 malloc 后是否有 NULL 检查
            alloc_vars = set()
            for pattern in self.memory_patterns['c']['alloc']:
                for match in re.finditer(pattern, code):
                    var_name = match.group(1)
                    alloc_vars.add(var_name)
                    line = code[:match.start()].count('\n') + func['start_line']
                    
                    # 检查是否有 NULL 检查
                    null_check_pattern = rf'if\s*\(\s*{re.escape(var_name)}\s*==\s*NULL'
                    if not re.search(null_check_pattern, code):
                        issues.append(MemoryIssue(
                            type="missing_null_check",
                            severity="medium",
                            file=file_path,
                            line=line,
                            description=f"变量 '{var_name}' 分配内存后未检查 NULL",
                            suggestion=f"在使用 {var_name} 前添加 NULL 检查"
                        ))
            
            # 检查是否有对应的 free
            for var in alloc_vars:
                free_pattern = rf'free\s*\(\s*{re.escape(var)}\s*\)'
                if not re.search(free_pattern, code):
                    issues.append(MemoryIssue(
                        type="potential_leak",
                        severity="high",
                        file=file_path,
                        line=func['start_line'],
                        description=f"变量 '{var}' 可能存在内存泄漏（函数内未释放）",
                        suggestion=f"确保在适当位置释放 {var}，或确认由调用者负责释放"
                    ))
            
            # 检查数组越界风险
            array_accesses = re.findall(r'(\w+)\s*\[\s*([^]]+)\s*\]', code)
            for arr, idx in array_accesses:
                # 检查索引是否可能越界
                if re.match(r'\d+', idx) and int(idx) > 1000:
                    line = code.find(f'{arr}[{idx}]')
                    line_num = code[:line].count('\n') + func['start_line'] if line > 0 else func['start_line']
                    issues.append(MemoryIssue(
                        type="large_index",
                        severity="low",
                        file=file_path,
                        line=line_num,
                        description=f"数组 '{arr}' 使用大索引 {idx}",
                        suggestion="确认数组大小足够"
                    ))
        
        elif language == 'python':
            # 检查大列表创建
            large_list_pattern = self.memory_patterns['python']['large_list']
            for match in re.finditer(large_list_pattern, code):
                line = code[:match.start()].count('\n') + func['start_line']
                issues.append(MemoryIssue(
                    type="large_allocation",
                    severity="medium",
                    file=file_path,
                    line=line,
                    description="创建大列表可能消耗大量内存",
                    suggestion="考虑使用生成器或迭代器"
                ))
        
        return issues
    
    def _check_alloc_free_pairs(self, functions: List[FunctionInfo]) -> List[MemoryIssue]:
        """检查 alloc/free 配对"""
        issues = []
        
        # 收集所有分配和释放
        all_allocs = {}  # var_name -> [(file, line, func)]
        all_frees = {}   # var_name -> [(file, line, func)]
        
        for func in functions:
            code = func.get("code_snippet", "")
            
            for pattern in self.memory_patterns['c']['alloc']:
                for match in re.finditer(pattern, code):
                    var = match.group(1)
                    line = code[:match.start()].count('\n') + func['start_line']
                    if var not in all_allocs:
                        all_allocs[var] = []
                    all_allocs[var].append((func['file'], line, func['name']))
            
            for match in re.finditer(self.memory_patterns['c']['free'], code):
                var = match.group(1)
                line = code[:match.start()].count('\n') + func['start_line']
                if var not in all_frees:
                    all_frees[var] = []
                all_frees[var].append((func['file'], line, func['name']))
        
        # 检查未释放的变量（简单检查）
        for var, allocs in all_allocs.items():
            if var not in all_frees:
                for file_path, line, func_name in allocs:
                    issues.append(MemoryIssue(
                        type="potential_leak",
                        severity="high",
                        file=file_path,
                        line=line,
                        description=f"'{var}' 在 {func_name} 中分配但未在分析范围内找到释放",
                        suggestion="确认内存是否在其他地方释放"
                    ))
        
        # 检查可能的重复释放
        for var, frees in all_frees.items():
            if len(frees) > 1:
                for file_path, line, func_name in frees[1:]:
                    issues.append(MemoryIssue(
                        type="potential_double_free",
                        severity="high",
                        file=file_path,
                        line=line,
                        description=f"'{var}' 可能被多次释放",
                        suggestion="检查释放逻辑，确保每个指针只释放一次"
                    ))
        
        return issues
    
    def _llm_memory_analyze(self, functions: List[FunctionInfo],
                            language: str) -> tuple[List[MemoryIssue], str]:
        """使用 LLM 进行内存分析"""
        # 选择可能有内存问题的函数
        candidates = []
        for func in functions:
            code = func.get("code_snippet", "").lower()
            if any(kw in code for kw in ['malloc', 'free', 'alloc', 'new', 'delete', 'buffer']):
                candidates.append(func)
        
        if not candidates:
            candidates = functions[:3]
        else:
            candidates = candidates[:5]
        
        code_samples = ""
        for func in candidates:
            code_samples += f"\n### {func['name']} ({func['file']}:{func['start_line']})\n"
            code_samples += f"```{language}\n{func.get('code_snippet', '')[:1000]}\n```\n"
        
        prompt = f"""
你是一个内存安全专家。分析以下 {language} 代码的内存使用情况。

{code_samples}

请分析：
1. 内存分配模式（静态/动态，大小）
2. 潜在的内存问题：
   - 内存泄漏
   - 重复释放
   - 使用已释放内存
   - 缓冲区溢出
   - 未初始化使用
3. 内存使用效率
4. 缓存友好性

输出两部分：

第一部分 - 问题列表（JSON）：
```json
[
  {{
    "type": "问题类型",
    "severity": "high/medium/low",
    "function": "函数名",
    "description": "问题描述",
    "suggestion": "修复建议"
  }}
]
```

第二部分 - 内存模式分析（Markdown）：
对整体内存使用模式的分析和建议。
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content
            
            # 解析问题 JSON
            import json
            issues = []
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                try:
                    problems = json.loads(json_match.group(1))
                    for prob in problems:
                        # 找到函数位置
                        func_name = prob.get("function", "")
                        file_path = ""
                        line = 0
                        for f in candidates:
                            if f["name"] == func_name:
                                file_path = f["file"]
                                line = f["start_line"]
                                break
                        
                        issues.append(MemoryIssue(
                            type=prob.get("type", "unknown"),
                            severity=prob.get("severity", "medium"),
                            file=file_path,
                            line=line,
                            description=prob.get("description", ""),
                            suggestion=prob.get("suggestion", "")
                        ))
                except json.JSONDecodeError:
                    pass
            
            # 提取 Markdown 分析
            memory_patterns = content.split("```")[-1].strip() if "```" in content else content
            
            logger.info(f"LLM 内存分析发现 {len(issues)} 个问题")
            return issues, memory_patterns
            
        except Exception as e:
            logger.warning(f"LLM 内存分析失败: {e}")
            return [], ""
    
    def _deduplicate_issues(self, issues: List[MemoryIssue]) -> List[MemoryIssue]:
        """去重"""
        seen = set()
        unique = []
        for issue in issues:
            key = (issue["type"], issue["file"], issue["line"])
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique
