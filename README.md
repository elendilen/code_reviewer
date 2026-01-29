# Complex Code Review System V2

一个基于 LangGraph 构建的智能代码审查系统，支持 **Python**, **C**, **Go** 多语言项目。

## 特性

- **Map-Reduce 并行架构**: 自动将大项目拆分为多个子任务并行审查
- **智能项目结构分析**: Agent 自主探索目录结构，生成项目架构文档
- **自动测试生成**: 为每个模块自动生成功能测试和性能测试
- **多语言支持**: Python (pytest), Go (go test), C (gcc)

## 架构

```
START
  │
  ▼
┌─────────────────────┐
│  analyze_structure  │  ← 项目结构分析 Agent (使用 list_dir, read_file 工具)
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│     plan_tasks      │  ← 任务分工 Agent (输出 JSON 任务列表)
└─────────────────────┘
  │
  │ ┌──── Send ────┐ ┌──── Send ────┐
  ▼ ▼              ▼ ▼              
┌─────────┐      ┌─────────┐
│ Worker  │      │ Worker  │  ← 并行 Worker (代码审查 + 测试生成)
│ Task A  │      │ Task B  │
└─────────┘      └─────────┘
  │              │
  └──────┬───────┘
         ▼
┌─────────────────────┐
│     run_tests       │  ← 测试执行 Agent (pytest/go test/gcc)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  generate_report    │  ← 最终报告生成
└─────────────────────┘
         │
         ▼
        END
```

## 目录结构

```
complex_code_review/
├── main.py                 # 入口文件
├── requirements.txt
├── reports/                # 生成的报告目录
├── tests/
│   ├── system/            # 系统自动生成的测试
│   └── user/              # 用户自定义测试
└── src/
    ├── agents/            # 智能代理
    │   ├── structure_agent.py   # 项目结构分析
    │   ├── planner_agent.py     # 任务分工
    │   ├── worker_agent.py      # 并行 Worker
    │   ├── test_runner.py       # 测试执行
    │   └── report_agent.py      # 报告生成
    ├── graph/
    │   └── workflow.py    # LangGraph 工作流定义
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

```bash
python main.py /path/to/your/project
```

### 4. 查看报告

报告将生成在 `reports/` 目录下：
- `project_structure.md` - 项目结构与功能文档
- `final_analysis.md` - 综合分析报告

## 配置

默认使用 `qwen2.5-coder:7b` 模型。如需修改，编辑各 Agent 文件中的 `model_name` 参数。

## 可视化流程图

```bash
python visualize_complex_graph.py
```

将生成 `complex_workflow_graph.png`。
