"""
Code Extractor Agent - 代码提取器
负责解析源代码，提取函数、数据结构、调用关系等关键信息
"""
import os
import re
from typing import List, Dict, Any, Tuple
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from .perf_state import PerformanceState, FunctionInfo, DataStructureInfo
from ..utils.logger import setup_logger

logger = setup_logger("code_extractor")


class CodeExtractorAgent:
    """代码提取器 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0)
        
        # 语言特定的正则模式
        self.patterns = {
            'c': {
                'function': r'(?:static\s+)?(?:inline\s+)?(\w+(?:\s*\*)*)\s+(\w+)\s*\(([^)]*)\)\s*\{',
                'struct': r'(?:typedef\s+)?struct\s+(\w+)?\s*\{([^}]*)\}(?:\s*(\w+))?;',
                'loop_for': r'for\s*\([^)]*\)',
                'loop_while': r'while\s*\([^)]*\)',
                'malloc': r'(\w+)\s*=\s*(?:malloc|calloc|realloc)\s*\(',
                'free': r'free\s*\(\s*(\w+)\s*\)',
            },
            'python': {
                'function': r'def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\w+))?:',
                'class': r'class\s+(\w+)(?:\s*\([^)]*\))?:',
                'loop_for': r'for\s+\w+\s+in\s+',
                'loop_while': r'while\s+',
            },
            'go': {
                'function': r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)(?:\s*\(?([^{]*)\)?)?\s*\{',
                'struct': r'type\s+(\w+)\s+struct\s*\{',
                'loop_for': r'for\s+',
            }
        }
    
    def extract(self, state: PerformanceState) -> Dict[str, Any]:
        """提取代码结构信息"""
        project_path = state["project_path"]
        source_files = state["source_files"]
        language = state.get("language", "c")
        
        logger.info(f"开始提取代码结构，项目: {project_path}")
        logger.info(f"源文件数量: {len(source_files)}, 语言: {language}")
        
        all_functions: List[FunctionInfo] = []
        all_data_structures: List[DataStructureInfo] = []
        call_graph: Dict[str, List[str]] = {}
        
        for file_path in source_files[:10]:  # 限制文件数量避免过长
            if not os.path.exists(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 使用正则提取基础结构
                functions = self._extract_functions_regex(content, file_path, language)
                data_structures = self._extract_data_structures_regex(content, file_path, language)
                
                all_functions.extend(functions)
                all_data_structures.extend(data_structures)
                
                # 构建调用图
                for func in functions:
                    call_graph[func["name"]] = func.get("calls", [])
                    
            except Exception as e:
                logger.warning(f"处理文件失败 {file_path}: {e}")
        
        # 使用 LLM 增强分析
        if all_functions:
            logger.info("使用 LLM 增强函数分析...")
            all_functions = self._enhance_with_llm(all_functions, language)
        
        logger.info(f"提取完成: {len(all_functions)} 个函数, {len(all_data_structures)} 个数据结构")
        
        return {
            "functions": all_functions,
            "data_structures": all_data_structures,
            "call_graph": call_graph
        }
    
    def _extract_functions_regex(self, content: str, file_path: str, 
                                  language: str) -> List[FunctionInfo]:
        """使用正则表达式提取函数"""
        functions = []
        lines = content.split('\n')
        
        pattern = self.patterns.get(language, {}).get('function')
        if not pattern:
            return functions
        
        for match in re.finditer(pattern, content):
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            
            # 找到函数结束位置（简单的大括号匹配）
            func_content, end_line = self._find_function_body(content, match.end(), start_line)
            
            # 提取函数调用
            calls = self._extract_function_calls(func_content, language)
            
            # 提取循环
            loops = self._extract_loops(func_content, language)
            
            # 检测递归
            func_name = match.group(2) if language == 'c' else match.group(1)
            recursion = func_name in calls
            
            functions.append(FunctionInfo(
                name=func_name,
                file=file_path,
                start_line=start_line,
                end_line=end_line,
                params=self._parse_params(match.group(3) if language == 'c' else match.group(2)),
                return_type=match.group(1) if language == 'c' else (match.group(3) or "None"),
                calls=calls,
                loops=loops,
                recursion=recursion,
                code_snippet=func_content[:1500]  # 限制长度
            ))
        
        return functions
    
    def _find_function_body(self, content: str, start: int, start_line: int) -> Tuple[str, int]:
        """找到函数体（简单的大括号匹配）"""
        brace_count = 1
        pos = start
        
        # 跳过开始的 {
        while pos < len(content) and content[pos] != '{':
            pos += 1
        pos += 1
        
        func_start = start
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        
        func_content = content[func_start:pos]
        end_line = start_line + func_content.count('\n')
        
        return func_content, end_line
    
    def _extract_function_calls(self, content: str, language: str) -> List[str]:
        """提取函数调用"""
        # 简单匹配函数调用模式: identifier(
        calls = re.findall(r'\b(\w+)\s*\(', content)
        # 过滤关键字
        keywords = {'if', 'while', 'for', 'switch', 'sizeof', 'return', 'typedef'}
        return list(set(c for c in calls if c not in keywords))
    
    def _extract_loops(self, content: str, language: str) -> List[Dict[str, Any]]:
        """提取循环结构"""
        loops = []
        patterns = self.patterns.get(language, {})
        
        for loop_type in ['loop_for', 'loop_while']:
            pattern = patterns.get(loop_type)
            if pattern:
                for match in re.finditer(pattern, content):
                    line = content[:match.start()].count('\n') + 1
                    loops.append({
                        "type": loop_type.replace('loop_', ''),
                        "line": line,
                        "content": match.group(0)[:100]
                    })
        
        return loops
    
    def _parse_params(self, params_str: str) -> List[str]:
        """解析参数列表"""
        if not params_str or params_str.strip() == 'void':
            return []
        return [p.strip() for p in params_str.split(',') if p.strip()]
    
    def _extract_data_structures_regex(self, content: str, file_path: str,
                                        language: str) -> List[DataStructureInfo]:
        """提取数据结构"""
        structures = []
        pattern = self.patterns.get(language, {}).get('struct')
        
        if pattern:
            for match in re.finditer(pattern, content):
                line = content[:match.start()].count('\n') + 1
                name = match.group(1) or match.group(3) or "anonymous"
                
                structures.append(DataStructureInfo(
                    name=name,
                    type="struct",
                    file=file_path,
                    line=line,
                    size="static",
                    operations=[]
                ))
        
        # 检测数组定义
        array_pattern = r'(\w+)\s+(\w+)\s*\[\s*(\w*)\s*\]'
        for match in re.finditer(array_pattern, content):
            line = content[:match.start()].count('\n') + 1
            size = "static" if match.group(3) else "dynamic"
            
            structures.append(DataStructureInfo(
                name=match.group(2),
                type="array",
                file=file_path,
                line=line,
                size=size,
                operations=[]
            ))
        
        return structures
    
    def _enhance_with_llm(self, functions: List[FunctionInfo], 
                          language: str) -> List[FunctionInfo]:
        """使用 LLM 增强函数分析"""
        # 选择最重要的函数进行深入分析
        important_funcs = sorted(functions, 
                                 key=lambda f: len(f.get("loops", [])) + len(f.get("calls", [])),
                                 reverse=True)[:5]
        
        if not important_funcs:
            return functions
        
        funcs_summary = ""
        for f in important_funcs:
            funcs_summary += f"\n### {f['name']} ({f['file']}:{f['start_line']}-{f['end_line']})\n"
            funcs_summary += f"参数: {f['params']}\n"
            funcs_summary += f"循环: {len(f['loops'])} 个\n"
            funcs_summary += f"代码:\n```{language}\n{f['code_snippet'][:800]}\n```\n"
        
        prompt = f"""
分析以下 {language} 函数，识别每个函数的：
1. 主要功能
2. 关键算法/逻辑
3. 潜在的性能关注点

{funcs_summary}

以 JSON 格式输出，格式：
{{
    "函数名": {{
        "purpose": "主要功能",
        "algorithm": "使用的算法/逻辑",
        "perf_concerns": ["性能关注点1", "性能关注点2"]
    }}
}}
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            # 这里可以解析 LLM 返回的 JSON 来增强函数信息
            # 简化处理：将分析结果记录到日志
            logger.info(f"LLM 函数分析完成")
        except Exception as e:
            logger.warning(f"LLM 分析失败: {e}")
        
        return functions
