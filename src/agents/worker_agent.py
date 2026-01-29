from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from ..state.state import WorkerState, ReviewResult
from ..tools.file_tools import read_file
from ..utils.logger import worker_logger as logger
import os

class WorkerAgent:
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.2)

    def review_code(self, state: WorkerState):
        """
        Perform syntax and performance check on the assigned files.
        """
        task = state["task"]
        project_path = state["project_path"]
        readme_content = state.get("readme_content", "")
        logger.info(f"[审查] 任务 {task['id']}: 读取 {len(task['files'])} 个文件")
        
        # Read all files for this task
        combined_code = ""
        for file_path in task["files"]:
            full_path = os.path.join(project_path, file_path)
            # 简单的路径处理，防止重复 path
            if file_path.startswith("/"):
                full_path = file_path
            
            content = read_file.invoke(full_path)
            combined_code += f"\n\n--- File: {file_path} ---\n{content}"

        # 截取 README 的关键部分作为项目背景
        readme_summary = readme_content[:1500] if readme_content else "(无项目说明)"

        prompt = f"""
        你是一个资深代码审查专家，精通 {task['language']} 语言。
        
        ## 项目背景（来自 README）:
        {readme_summary}
        
        ## 当前审查任务:
        - 模块名称: {task['name']}
        - 模块描述: {task['description']}
        - 包含文件: {task['files']}
        
        ## 代码内容:
        {combined_code[:20000]}
        
        请根据项目背景，进行《局部代码检查》，包含以下部分：
        
        1. **功能理解**：根据项目背景，说明这个模块在整体项目中的作用。
        2. **语法与规范**：检查语法错误、编码风格问题。
        3. **性能分析**：
           - 分析关键函数的时间/空间复杂度
           - 指出性能瓶颈和热点代码
           - 检查是否有内存泄漏风险（对于 C 语言）
        4. **潜在 Bug**：检查可能的逻辑错误、边界条件问题。
        5. **改进建议**：给出具体的优化和修复建议。
        
        输出要求：
        - Markdown 格式
        - 明确指出问题所在的文件和行号
        - 给出具体的代码修复示例
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        
        result = ReviewResult(
            task_id=task["id"],
            content=response.content,
            issues=[] # TODO: Can be parsed to structured data
        )
        
        # Parallel: Return a list update for 'reviews' key in global state
        return {"reviews": [result]}
