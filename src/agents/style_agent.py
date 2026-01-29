from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from ..state.state import OverallState
from ..tools.file_tools import list_directory, read_file
from ..utils.logger import style_logger as logger
import os

class GlobalStyleAgent:
    """全局代码风格检查 Agent"""
    
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1)

    def check(self, state: OverallState):
        """
        Perform global style check on the project.
        This runs in parallel with structure analysis.
        """
        project_path = state["project_path"]
        logger.info(f"开始全局风格检查: {project_path}")
        
        # Collect sample files for style analysis
        sample_code = ""
        files_checked = []
        
        def collect_files(path, depth=0):
            nonlocal sample_code, files_checked
            if depth > 2:  # Limit recursion depth
                return
            try:
                items = list_directory.invoke(path)
                for item in items:
                    if item.startswith('.') or item in ['__pycache__', 'node_modules', 'venv', '.git']:
                        continue
                    full_path = os.path.join(path, item)
                    if os.path.isfile(full_path):
                        ext = os.path.splitext(item)[1]
                        if ext in ['.py', '.c', '.h', '.go', '.js', '.ts']:
                            content = read_file.invoke(full_path)
                            if len(sample_code) < 10000:  # Limit total size
                                sample_code += f"\n\n--- {full_path} ---\n{content[:2000]}"
                                files_checked.append(full_path)
                    elif os.path.isdir(full_path):
                        collect_files(full_path, depth + 1)
            except Exception as e:
                pass
        
        collect_files(project_path)
        
        prompt = f"""
        你是一个代码风格审查专家。请对以下项目代码进行全局风格检查。
        
        检查的文件: {files_checked}
        
        代码样本:
        {sample_code}
        
        请分析：
        1. **命名规范一致性**: 变量、函数、类的命名是否遵循统一风格
        2. **代码格式**: 缩进、空格、换行是否一致
        3. **注释质量**: 是否有足够的文档和注释
        4. **代码组织**: 文件结构、模块划分是否合理
        5. **最佳实践**: 是否遵循语言特定的最佳实践
        
        输出要求：
        - Markdown 格式
        - 给出整体风格评分 (1-10)
        - 列出主要问题和改进建议
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        return {"global_style_report": response.content}
