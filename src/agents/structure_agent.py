from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from ..tools.file_tools import list_directory, read_file
from ..state.state import OverallState
from ..utils.logger import structure_logger as logger
from langchain_core.runnables import RunnableConfig

class ProjectStructureAgent:
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)
        self.tools = [list_directory, read_file]
        # For LangGraph agent, we usually bind tools
        self.model_with_tools = self.llm.bind_tools(self.tools)

    def analyze(self, state: OverallState, config: RunnableConfig):
        """
        Analyze project structure.
        This node acts as an agent that can call tools to explore the directory.
        Recursively explores subdirectories to find all source files.
        """
        project_path = state["project_path"]
        logger.info(f"分析项目路径: {project_path}")
        
        import os
        
        # 递归收集目录结构和源代码文件
        def collect_structure(path, depth=0, max_depth=4):
            """递归收集目录结构"""
            if depth > max_depth:
                return []
            
            result = []
            try:
                items = list_directory.invoke(path)
                for item in items:
                    # 跳过隐藏文件和常见的非源码目录
                    if item.startswith('.') or item in ['__pycache__', 'node_modules', 'venv', 'build', '.git']:
                        continue
                    
                    full_path = os.path.join(path, item)
                    rel_path = os.path.relpath(full_path, project_path)
                    indent = "  " * depth
                    
                    if os.path.isdir(full_path):
                        result.append(f"{indent}├── {item}/")
                        result.extend(collect_structure(full_path, depth + 1, max_depth))
                    else:
                        result.append(f"{indent}├── {item}")
            except Exception as e:
                logger.warning(f"无法读取目录 {path}: {e}")
            return result
        
        # 收集所有源代码文件内容
        def collect_source_files(path, max_files=10, max_size=15000):
            """递归收集源代码文件内容"""
            source_files = {}
            total_size = 0
            
            def _collect(p):
                nonlocal total_size
                if total_size > max_size or len(source_files) >= max_files:
                    return
                try:
                    items = list_directory.invoke(p)
                    for item in items:
                        if item.startswith('.') or item in ['__pycache__', 'node_modules', 'venv', 'build', '.git']:
                            continue
                        full_path = os.path.join(p, item)
                        if os.path.isdir(full_path):
                            _collect(full_path)
                        else:
                            ext = os.path.splitext(item)[1]
                            # 收集源代码文件
                            if ext in ['.c', '.h', '.go', '.py', '.js', '.ts']:
                                if len(source_files) < max_files and total_size < max_size:
                                    content = read_file.invoke(full_path)
                                    rel_path = os.path.relpath(full_path, project_path)
                                    # 截断过长的文件
                                    if len(content) > 3000:
                                        content = content[:3000] + "\n... (truncated)"
                                    source_files[rel_path] = content
                                    total_size += len(content)
                except Exception as e:
                    pass
            
            _collect(path)
            return source_files
        
        logger.info("读取项目根目录...")
        files = list_directory.invoke(project_path)
        logger.info(f"发现 {len(files)} 个文件/目录")
        
        # 递归收集目录结构
        logger.info("递归收集目录结构...")
        tree_lines = collect_structure(project_path)
        tree_str = "\n".join(tree_lines)
        
        # 收集源代码文件
        logger.info("收集源代码文件内容...")
        source_files = collect_source_files(project_path)
        logger.info(f"找到 {len(source_files)} 个源代码文件")
        
        # 格式化源代码内容
        source_content = ""
        for fpath, content in source_files.items():
            source_content += f"\n\n=== {fpath} ===\n{content}"
        
        # 读取 README
        readme_content = ""
        for f in files:
            if f.lower().startswith("readme"):
                readme_content = read_file.invoke(f"{project_path}/{f}")
                break
                
        prompt = f"""
        你是一个高级项目架构师。你的任务是分析位于 '{project_path}' 的项目结构。
        
        ## 完整目录结构树:
        ```
        {project_path}/
        {tree_str}
        ```
        
        ## README 内容:
        {readme_content[:1500] if readme_content else "(无 README)"}
        
        ## 核心源代码文件内容:
        {source_content}
        
        请生成一份详细的《项目结构、核心算法与数据结构文档》(Markdown格式)。
        文档应包含：
        
        ## 1. 项目概述
        - 项目使用的主要编程语言 (Python, C, Go, 等)
        - 项目的整体功能和用途
        
        ## 2. 目录结构
        - 目录树及其作用说明
        - 特别关注包含源代码的目录
        
        ## 3. 核心模块划分
        - 模块功能划分（基于实际的源代码文件）
        - 模块间的依赖关系
        
        ## 4. 核心数据结构
        - 列出代码中定义的所有重要数据结构（struct、class、enum 等）
        - 详细解释每个数据结构的字段含义和用途
        - 说明数据结构之间的关系
        
        ## 5. 核心算法
        - 识别代码中使用的核心算法（如哈希算法、缓存淘汰算法、排序算法等）
        - 详细解释每个算法的实现原理
        - 分析算法的时间/空间复杂度
        
        ## 6. 关键文件说明
        - 入口文件 (如 main.c, main.py)
        - 核心逻辑文件 (实现主要功能的文件)
        - 头文件/接口文件
        
        ## 7. 源代码文件清单
        - 列出所有发现的源代码文件的相对路径
        
        【重要】请确保列出所有发现的源代码文件的相对路径，而不是虚构的路径。
        请深入分析代码，详细描述数据结构和算法的实现细节。
        """
        
        logger.info("调用 LLM 生成项目结构文档...")
        response = self.llm.invoke([HumanMessage(content=prompt)])
        logger.info(f"结构文档生成完成，长度: {len(response.content)} 字符")
        logger.info(f"README 内容长度: {len(readme_content)} 字符")
        return {
            "structure_doc": response.content,
            "readme_content": readme_content  # 保存 README 供后续节点使用
        }
