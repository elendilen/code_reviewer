from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from ..state.state import OverallState, TestResult
from ..tools.test_tools import run_shell_command
from ..utils.logger import test_runner_logger as logger
from typing import List, Dict
import os

class TestRunnerAgent:
    """
    测试运行 Agent - 完全基于用户自定义测试
    支持：
    1. 指定测试命令列表
    2. 指定测试目录（运行目录中所有测试脚本）
    """
    def __init__(self, model_name="qwen2.5-coder:7b", base_url="http://localhost:11434"):
        self.llm = ChatOllama(model=model_name, base_url=base_url)

    def run_tests(self, state: OverallState):
        """
        运行用户自定义测试并分析结果。
        
        支持两种测试来源：
        1. custom_test_commands: 用户指定的命令列表
        2. test_dir: 用户指定的测试目录（运行其中所有脚本）
        """
        project_path = state["project_path"]
        custom_test_commands = state.get("custom_test_commands", [])
        test_dir = state.get("test_dir", "")  # 用户指定的测试目录
        
        logger.info(f"准备运行用户自定义测试，项目: {project_path}")
        logger.info(f"自定义测试命令: {len(custom_test_commands)} 个")
        logger.info(f"测试目录: {test_dir or '未指定'}")
        
        # 收集所有测试执行信息
        test_executions: List[Dict] = []
        overall_success = True
        
        # ============ 1. 运行用户指定的测试命令 ============
        if custom_test_commands:
            logger.info("=== 运行用户自定义测试命令 ===")
            for i, cmd in enumerate(custom_test_commands, 1):
                logger.info(f"执行测试命令 {i}: {cmd}")
                
                execution = self._run_single_test(
                    project_path=project_path,
                    test_name=f"自定义命令 {i}",
                    test_cmd=cmd,
                    script_content=None  # 命令没有脚本内容
                )
                test_executions.append(execution)
                
                if not execution["success"]:
                    overall_success = False
        
        # ============ 2. 运行测试目录中的所有脚本 ============
        if test_dir:
            # 支持相对路径和绝对路径
            if not os.path.isabs(test_dir):
                test_dir = os.path.join(project_path, test_dir)
            
            if os.path.isdir(test_dir):
                logger.info(f"=== 扫描测试目录: {test_dir} ===")
                dir_tests = self._collect_tests_from_dir(test_dir)
                logger.info(f"发现 {len(dir_tests)} 个测试脚本")
                
                for test_info in dir_tests:
                    logger.info(f"执行: {test_info['name']}")
                    
                    execution = self._run_single_test(
                        project_path=project_path,
                        test_name=test_info["name"],
                        test_cmd=test_info["cmd"],
                        script_content=test_info.get("content")
                    )
                    test_executions.append(execution)
                    
                    if not execution["success"]:
                        overall_success = False
            else:
                logger.warning(f"测试目录不存在: {test_dir}")
        
        # ============ 3. 如果没有任何测试，记录信息 ============
        if not test_executions:
            logger.warning("未指定任何测试命令或测试目录")
            test_executions.append({
                "name": "无测试",
                "cmd": "",
                "script_content": "",
                "output": "未指定任何测试。请使用 -t 参数指定测试命令，或使用 --test-dir 参数指定测试目录。",
                "success": True
            })
        
        # ============ 4. 调用 LLM 分析测试结果 ============
        logger.info("调用 LLM 分析测试结果...")
        analysis = self._analyze_test_results(test_executions, project_path)
        
        # 构建完整的测试报告
        full_report = self._build_test_report(test_executions, analysis)
        
        logger.info(f"测试执行完成，总体成功: {overall_success}")
        
        new_result = TestResult(
            task_id="user_tests",
            test_files_generated=[],  # 不生成测试文件
            execution_output=full_report,
            success=overall_success
        )
        
        return {"test_results": [new_result]}

    def _run_single_test(self, project_path: str, test_name: str, 
                         test_cmd: str, script_content: str = None) -> Dict:
        """
        执行单个测试并返回结果。
        """
        full_cmd = f"cd {project_path} && {test_cmd} 2>&1"
        
        try:
            output = run_shell_command.invoke(full_cmd)
            
            # 检查是否失败
            success = True
            failure_indicators = [
                "FAILED", "ERROR", "error:", "FAIL:", 
                "Segmentation fault", "core dumped",
                "assertion failed", "AssertionError"
            ]
            for indicator in failure_indicators:
                if indicator.lower() in output.lower():
                    success = False
                    break
            
            # 也检查返回码（如果输出中包含）
            if "exit code" in output.lower() or "returned" in output.lower():
                if "exit code 1" in output.lower() or "returned 1" in output.lower():
                    success = False
            
            logger.info(f"   └─ {test_name}: {'✅ 通过' if success else '❌ 失败'}")
            
            return {
                "name": test_name,
                "cmd": test_cmd,
                "script_content": script_content or "",
                "output": output,
                "success": success
            }
            
        except Exception as e:
            logger.error(f"   └─ {test_name}: 执行异常 - {e}")
            return {
                "name": test_name,
                "cmd": test_cmd,
                "script_content": script_content or "",
                "output": f"执行异常: {str(e)}",
                "success": False
            }

    def _collect_tests_from_dir(self, test_dir: str) -> List[Dict]:
        """
        收集测试目录中的所有测试脚本。
        支持: .sh, .py, .go, .c 等格式
        """
        tests = []
        
        for root, dirs, files in os.walk(test_dir):
            for f in sorted(files):
                file_path = os.path.join(root, f)
                rel_path = os.path.relpath(file_path, test_dir)
                
                # 读取脚本内容
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read()
                except Exception as e:
                    content = f"(无法读取: {e})"
                
                # 根据文件类型确定运行命令
                if f.endswith('.sh'):
                    tests.append({
                        "name": rel_path,
                        "cmd": f"bash {file_path}",
                        "content": content
                    })
                elif f.endswith('.py'):
                    tests.append({
                        "name": rel_path,
                        "cmd": f"python3 {file_path}",
                        "content": content
                    })
                elif f.endswith('_test.go') or f.endswith('_test.go'):
                    # Go 测试文件需要在其目录下运行
                    tests.append({
                        "name": rel_path,
                        "cmd": f"cd {root} && go test -v -run .",
                        "content": content
                    })
                elif f.endswith('.c') and 'test' in f.lower():
                    # C 测试文件需要先编译
                    exe_name = f.replace('.c', '')
                    tests.append({
                        "name": rel_path,
                        "cmd": f"gcc -o /tmp/{exe_name} {file_path} && /tmp/{exe_name}",
                        "content": content
                    })
        
        return tests

    def _analyze_test_results(self, test_executions: List[Dict], project_path: str) -> str:
        """
        使用 LLM 分析测试结果，提供详细的测试报告分析。
        """
        # 构建测试摘要
        test_summary = ""
        for i, exe in enumerate(test_executions, 1):
            status = "✅ PASS" if exe["success"] else "❌ FAIL"
            test_summary += f"\n## 测试 {i}: {exe['name']} [{status}]\n"
            test_summary += f"命令: `{exe['cmd']}`\n"
            
            if exe.get("script_content"):
                # 截取脚本内容（不要太长）
                script_preview = exe["script_content"][:2000]
                if len(exe["script_content"]) > 2000:
                    script_preview += "\n... (内容已截断)"
                test_summary += f"\n### 脚本内容:\n```\n{script_preview}\n```\n"
            
            # 截取输出
            output_preview = exe["output"][:3000]
            if len(exe["output"]) > 3000:
                output_preview += "\n... (输出已截断)"
            test_summary += f"\n### 执行输出:\n```\n{output_preview}\n```\n"
        
        prompt = f"""
你是一名测试分析专家。请分析以下测试执行结果并给出详细的分析报告。

项目路径: {project_path}

{test_summary}

请提供以下分析：

1. **测试结果概览**：
   - 总测试数、通过数、失败数
   - 整体通过率

2. **失败测试分析**（如有）：
   - 失败原因分析
   - 可能的根本原因
   - 修复建议

3. **测试覆盖评估**：
   - 当前测试覆盖了哪些功能点
   - 建议补充的测试场景

4. **测试质量建议**：
   - 测试脚本的改进建议
   - 测试效率优化建议

输出要求：
- 使用 Markdown 格式
- 重点突出问题和建议
- 给出具体可行的改进方案
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            return f"测试分析失败: {e}"

    def _build_test_report(self, test_executions: List[Dict], analysis: str) -> str:
        """
        构建完整的测试报告。
        """
        report = "# 用户自定义测试报告\n\n"
        
        # 统计信息
        total = len(test_executions)
        passed = sum(1 for e in test_executions if e["success"])
        failed = total - passed
        
        report += "## 测试统计\n\n"
        report += f"- 总测试数: {total}\n"
        report += f"- 通过: {passed} ✅\n"
        report += f"- 失败: {failed} ❌\n"
        report += f"- 通过率: {passed/total*100:.1f}%\n\n" if total > 0 else ""
        
        # 详细执行结果
        report += "## 测试执行详情\n\n"
        for i, exe in enumerate(test_executions, 1):
            status = "✅ PASS" if exe["success"] else "❌ FAIL"
            report += f"### {i}. {exe['name']} [{status}]\n\n"
            report += f"**命令**: `{exe['cmd']}`\n\n"
            
            if exe.get("script_content"):
                report += "<details>\n<summary>脚本内容</summary>\n\n"
                report += f"```bash\n{exe['script_content'][:2000]}\n```\n"
                report += "</details>\n\n"
            
            report += "**输出**:\n"
            report += f"```\n{exe['output'][:5000]}\n```\n\n"
        
        # LLM 分析
        report += "## 测试分析\n\n"
        report += analysis
        
        return report
