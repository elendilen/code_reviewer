from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from ..state.state import OverallState
from ..utils.logger import report_logger as logger

class FinalReportAgent:
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url)

    def generate(self, state: OverallState):
        structure_doc = state["structure_doc"]
        global_style = state.get("global_style_report", "")
        reviews = state["reviews"]
        test_results = state["test_results"]
        
        logger.info("开始生成最终报告")
        logger.info(f"   └─ 结构文档: {len(structure_doc)} 字符")
        logger.info(f"   └─ 风格报告: {len(global_style)} 字符")
        logger.info(f"   └─ 审查结果: {len(reviews)} 个")
        logger.info(f"   └─ 测试结果: {len(test_results)} 个")
        
        # Combine partial reviews
        reviews_text = ""
        for r in reviews:
            reviews_text += f"\n\n## 模块: {r['task_id']}\n{r['content']}"
            
        # Combine test results
        test_text = ""
        for t in test_results:
            if t['task_id'] == 'overall_run':
                 test_text += f"\n\n## 整体测试运行结果\n{t['execution_output']}"
            else:
                 test_text += f"\n- 模块 {t['task_id']} 生成测试文件: {t.get('test_files_generated', [])}"
                 
        prompt = f"""
        你是一份技术文档的总编。请根据以下资料，生成一份《综合代码审查与系统分析报告》。
        此报告将作为整个项目的最终交付文档。
        
        1. **项目结构与功能**:
        {structure_doc}
        
        2. **全局代码风格评估**:
        {global_style}
        
        3. **局部代码审查结果** (语法、规范、性能):
        {reviews_text}
        
        4. **测试执行情况**:
        {test_text}
        
        **报告要求**：
        1. **Markdown 格式**。
        2. **全面而详细**：不仅仅是拼接，要进行综合分析。
        3. **结构建议**：
           - 项目概览
           - 详细功能架构
           - 代码质量综合评估 (包含性能、风格)
           - 测试覆盖与结果分析
           - 问题汇总与修复建议 (Priority List)
        4. 语言风格专业、客观。
        """
        
        logger.info("调用 LLM 生成综合报告...")
        response = self.llm.invoke([HumanMessage(content=prompt)])
        logger.info(f"报告生成完成，长度: {len(response.content)} 字符")
        return {"final_report": response.content}
