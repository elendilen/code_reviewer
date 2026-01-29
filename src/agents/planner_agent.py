from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from ..state.state import OverallState, Task
from ..utils.logger import planner_logger as logger
import json

class PlannerAgent:
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        # JSON mode is helpful if supported, otherwise prompt engineering
        self.llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.1, format="json")

    def plan(self, state: OverallState):
        """
        Divide the project into tasks.
        """
        structure_doc = state["structure_doc"]
        project_path = state["project_path"]
        readme_content = state.get("readme_content", "")
        logger.info(f"开始规划任务分工，项目: {project_path}")
        logger.info(f"结构文档长度: {len(structure_doc)} 字符")
        logger.info(f"README 长度: {len(readme_content)} 字符")
        
        # 先扫描实际存在的源文件
        import os
        actual_files = []
        
        def scan_files(path):
            try:
                for item in os.listdir(path):
                    if item.startswith('.') or item in ['__pycache__', 'node_modules', 'venv', 'build', '.git', 'tests']:
                        continue
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        scan_files(full_path)
                    else:
                        ext = os.path.splitext(item)[1]
                        if ext in ['.c', '.h', '.go', '.py', '.js', '.ts', '.sh']:
                            rel_path = os.path.relpath(full_path, project_path)
                            actual_files.append(rel_path)
            except Exception as e:
                pass
        
        scan_files(project_path)
        logger.info(f"扫描到 {len(actual_files)} 个实际源文件: {actual_files}")
        
        # 截取 README 的关键部分
        readme_summary = readme_content[:2000] if readme_content else "(无 README)"
        
        prompt = f"""
        你是一个项目经理。根据以下项目信息，将项目划分为若干个具体的代码审查任务模块。
        
        ## 项目 README（项目背景和功能说明）:
        {readme_summary}
        
        ## 项目结构文档：
        {structure_doc}
        
        ## 【重要】实际存在的源代码文件列表（你必须只使用这些路径）：
        {actual_files}
        
        分工要求：
        1. 根据 README 中的项目功能说明，理解项目的核心目标。
        2. 将项目拆分为逻辑独立的功能模块。
        3. 每个任务的 files 字段必须只包含上面"实际存在的源代码文件列表"中的路径。
        4. 【严禁】虚构任何文件路径！只能使用上面列出的文件。
        5. 识别每个模块的主要语言（python, c, go, shell）。
        6. 确保所有实际文件都被分配到某个任务中。
        7. 将核心功能代码作为独立的高优先级任务。
        
        输出格式（JSON）：
        {{
            "tasks": [
                {{
                    "id": "task_1",
                    "name": "Core Logic",
                    "files": ["src/main.c", "src/utils.c"],
                    "description": "",
                    "language": "c"
                }}
            ]
        }}
        
        注意：files 数组中的路径必须是相对于项目根目录的相对路径。
        """
        
        logger.info("调用 LLM 进行任务规划...")
        response = self.llm.invoke([HumanMessage(content=prompt)])
        logger.info("LLM 响应完成，解析任务列表...")
        try:
            data = json.loads(response.content)
            tasks = data.get("tasks", [])
            # Normalize tasks to Task TypedDict
            normalized_tasks = []
            for t in tasks:
                normalized_tasks.append(Task(
                    id=t.get("id"),
                    name=t.get("name"),
                    files=t.get("files", []),
                    description=t.get("description", ""),
                    language=t.get("language", "unknown")
                ))
            logger.info(f"成功解析 {len(normalized_tasks)} 个任务")
            for t in normalized_tasks:
                logger.info(f"   └─ {t['id']}: {t['name']} ({len(t.get('files', []))} 个文件)")
            return {"tasks": normalized_tasks}
        except json.JSONDecodeError:
            logger.error(f"解析任务 JSON 失败: {response.content[:200]}...")
            return {"tasks": []}
