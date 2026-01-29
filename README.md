# Complex Code Review System V2

一个基于 LangGraph 构建的智能代码审查系统，支持 **Python**, **C**, **Go** 多语言项目。

## 特性

- **Map-Reduce 并行架构**: 自动将大项目拆分为多个子任务并行审查
- **智能项目结构分析**: Agent 自主探索目录结构，生成项目架构文档
- **自动测试生成**: 为每个模块自动生成功能测试和性能测试
- **多语言支持**: Python (pytest), Go (go test), C (gcc)

## 架构

![alt text](complex_workflow_graph.png)
![alt text](performance_workflow_graph.png)

## 目录结构

```
complex_code_review/
├── main.py                 # 入口文件
├── requirements.txt
├── reports/                # 生成的报告目录
└── src/
    ├── agents/            # 智能代理
    │   ├── structure_agent.py   # 项目结构分析
    │   ├── planner_agent.py     # 任务分工
    │   ├── worker_agent.py      # 并行 Worker
    │   ├── test_runner.py       # 测试执行
    │   └── report_agent.py      # 报告生成
    ├── graph/
    │   └── workflow.py    # LangGraph 工作流定义
    ├── performance/       # 性能分析子图（热点/内存/动态剖析/优化建议）
    │   ├── perf_workflow.py      # 性能子图定义（extract_code -> analyze_memory/profile -> detect_hotspots -> generate_optimizations）
    │   ├── perf_state.py         # 性能子图状态
    │   ├── code_extractor.py     # 代码结构提取
    │   ├── memory_analyzer.py    # 内存风险点分析
    │   ├── profiler_agent.py     # 动态剖析（time/perf 等，终端实时输出 + 指标解析）
    │   ├── hotspot_detector.py   # 热点定位
    │   ├── optimization_advisor.py # 优化建议 + 性能报告生成
    ├── state/
    │   └── state.py       # 状态定义 (TypedDict)
    └── tools/
        ├── file_tools.py  # 文件操作工具
        └── test_tools.py  # 命令执行工具
```

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 确保 Ollama 运行中

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

### 3. 运行审查

**基本用法**：

```bash
python main.py /path/to/your/project
```

```bash
usage: main.py [-h] [-t TEST_COMMANDS] [--test-dir TEST_DIR] [--perf] [--profile]
               [--exec PROFILING_EXECUTABLE] [--exec-arg PROFILING_EXEC_ARGS]
               [--exec-args PROFILING_EXEC_ARGS_STR] [--exec-cwd PROFILING_CWD] [--serve] [--port PORT]
               [-q]
               project_path

Complex Code Review System V2 - 代码审查与测试分析系统

positional arguments:
  project_path          要审查的项目路径

options:
  -h, --help            show this help message and exit
  -t, --test TEST_COMMANDS
                        自定义测试命令（可多次使用）
  --test-dir TEST_DIR   测试目录路径（运行其中所有脚本）
  --perf                启用深度性能分析（热点检测、内存分析、优化建议）
  --profile             启用动态性能剖析（需要可执行文件；可用 --exec/--exec-arg 指定运行方式）
  --exec PROFILING_EXECUTABLE
                        动态剖析时指定可执行文件路径（默认自动在项目中查找）
  --exec-arg PROFILING_EXEC_ARGS
                        动态剖析时传给可执行文件的参数（可多次使用）
  --exec-args PROFILING_EXEC_ARGS_STR
                        动态剖析时传给可执行文件的参数字符串（会用 shlex 拆分）
  --exec-cwd PROFILING_CWD
                        动态剖析运行工作目录（默认项目根目录）
  --serve               审查完成后启动 Web 服务器查看报告
  --port PORT           Web 服务器端口 (默认: 8080)
  -q, --quiet           安静模式，不渲染中间结果

示例用法:
  # 基本审查（无测试）
  python main.py /path/to/project

  # 指定测试命令
  python main.py /path/to/project -t "make test" -t "./run_tests.sh"

  # 指定测试目录（运行目录中所有脚本）
  python main.py /path/to/project --test-dir scripts/

  # 启用深度性能分析
  python main.py /path/to/project --perf

  # 完整分析（性能分析 + 动态剖析）
  python main.py /path/to/project --perf --profile

  # 审查完成后启动 Web 服务器查看报告
  python main.py /path/to/project --perf --serve
```

### 4. 查看报告

报告将生成在 `reports/` 目录下（仅保存核心文档）：
- `project_structure.md` - 项目结构与架构说明
- `performance_analysis.md` - 深度性能分析报告（仅在启用 --perf 时生成）
- `style_report.md` - 代码风格检查报告

## 配置

默认使用 `qwen2.5-coder:7b` 模型。如需修改，编辑各 Agent 文件中的 `model_name` 参数。

## 可视化流程图

```bash
python visualize_complex_graph.py
python visualize_performance_graph.py
```

将生成 `complex_workflow_graph.png` 和 `performance_workflow_graph.png`。
