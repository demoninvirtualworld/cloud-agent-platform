# DScode — Cloud Agent Platform

> 基于 Python 的 AI Agent 工具框架，对标 Claude Code 工具系统设计。让大语言模型通过 Function Calling 机制主动调用各类工具，在交互式终端中完成复杂的编程与问题求解任务。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-0.1.0-orange)]()

---

## ✨ 核心特性

- 🤖 **交互式 AI Agent**：双循环架构（REPL + Tool Calling），支持多轮对话与连续工具调用
- 🔧 **16 个内置工具**：文件读写、代码搜索、Shell 执行、Web 搜索/抓取、任务管理、子代理等
- 💬 **会话持久化**：JSON 文件存储会话历史，支持断点续传
- 🔒 **计划模式**：在编写代码前限制破坏性操作，需用户审批解锁
- 🔄 **子代理与工作流**：支持子代理并行执行，DAG 拓扑排序编排多代理工作流
- ⏰ **定时任务调度**：Cron 表达式 + asyncio 调度引擎
- 🎯 **技能系统**：动态加载 `.claude/skills/` 下的 Python 模块，支持热扩展
- 🌐 **多 LLM 后端兼容**：支持任何 OpenAI 兼容接口（DeepSeek / OpenAI / Ollama / vLLM）
- 🖥️ **跨平台终端**：prompt_toolkit 增强输入 + 自动 fallback，兼容各种终端环境

---

## 📦 项目结构

```
cloud agent platform/
├── main.py                  # CLI 入口（argparse 子命令 + 命令分发）
├── config.py                # 配置加载（从 config.json 读取 LLM 等设置）
├── config.json.example      # 配置文件模板
├── pyproject.toml           # 项目元数据与依赖声明
├── requirements.txt         # 锁定版本的依赖
│
├── agent/                   # Agent 核心引擎
│   └── agent.py             #   双循环编排（外层 REPL + 内层 Tool Calling）
│
├── llmapi/                  # LLM 接口层
│   └── LLMAPI.py            #   OpenAI 兼容客户端 + 流式响应 + 推理链支持
│
├── tools/                   # 工具系统（16 个工具）
│   ├── base.py              #   BaseTool 抽象基类 + ToolResult 统一返回
│   ├── registry.py          #   ToolRegistry 注册表（全局单例共享）
│   ├── read_file.py         #   读取文件（分页 + 行号）
│   ├── write_file.py        #   写入/创建文件
│   ├── edit_file.py         #   精确字符串替换
│   ├── run_bash.py          #   异步 Shell 命令执行
│   ├── glob_search.py       #   Glob 模式文件搜索
│   ├── grep_search.py       #   正则内容搜索（3 种输出模式）
│   ├── web_search.py        #   互联网搜索（DuckDuckGo / SerpAPI / Brave）
│   ├── web_fetch.py         #   网页内容抓取
│   ├── ask_user.py          #   交互式用户提问
│   ├── task_create.py       #   创建结构化任务项
│   ├── task_update.py       #   更新任务状态 + 依赖追踪
│   ├── start_agent.py       #   启动子代理（前后台模式）
│   ├── enter_plan_mode.py   #   计划模式（限制破坏性工具）
│   ├── create_cron.py       #   定时任务调度
│   ├── run_workflow.py      #   多代理工作流编排（DAG 拓扑排序）
│   └── use_skill.py         #   技能加载与执行
│
├── session/                 # 会话管理
│   ├── models.py            #   Pydantic 数据模型（Message / Session）
│   └── manager.py           #   SessionManager CRUD（JSON 文件存储）
│
├── ui/                      # 终端交互界面
│   ├── input_handler.py     #   prompt_toolkit 输入封装（Tab 补全、多行）
│   └── completer.py         #   自动补全器（/ 命令 + @ 文件路径）
│
├── tests/                   # 测试套件（104 个测试全部通过）
│   ├── conftest.py
│   ├── test_tools_base.py
│   ├── test_tools_registry.py
│   ├── test_session_models.py
│   └── test_session_manager.py
│
└── memory/sessions/         # 会话持久化目录（运行时生成）
```

---

## 🚀 快速开始

### 环境要求

- **Python** ≥ 3.10
- **配置**：OpenAI 兼容的 LLM API（如 DeepSeek、OpenAI、Ollama 等）

### 安装

```bash
# 1. 克隆仓库
git clone <repository-url>
cd "cloud agent platform"

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows

# 3. 安装项目及依赖（开发模式）
pip install -e .

# 4. 安装开发依赖（可选，含 pytest）
pip install -e ".[dev]"
```

### 配置

```bash
# 复制配置模板并填入你的 LLM API 信息
cp config.json.example config.json
```

编辑 `config.json`：

```json
{
    "llm": {
        "model_id": "deepseek-chat",
        "api_key": "your-api-key",
        "base_url": "https://api.deepseek.com",
        "timeout": 60
    },
    "search": {
        "backend": "duckduckgo",
        "api_key": ""
    }
}
```

### 运行

```bash
# 启动交互式对话（默认配置）
DScode

# 或使用
python main.py

# 创建指定配置的会话
DScode create --name my-agent --effort medium --max-turns 100

# 列出所有已保存会话
DScode list

# 恢复历史会话
DScode resume --id <session-id>

# 删除指定会话
DScode delete --id <session-id>

# 显示版本信息
DScode version
```

---

## 🛠️ 可用工具一览

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `read_file` | 读取文件内容，支持分页和行范围 | `file_path`, `offset`, `limit` |
| `write_file` | 覆写或创建文件 | `file_path`, `content` |
| `edit_file` | 精确字符串替换（单次 / 全部） | `file_path`, `old_string`, `new_string`, `replace_all` |
| `run_bash` | 异步 Shell 命令执行 | `command`, `timeout`, `workdir` |
| `glob_search` | Glob 模式文件搜索 | `pattern`, `path` |
| `grep_search` | 正则内容搜索（3 种输出模式） | `pattern`, `path`, `glob`, `output_mode` |
| `web_search` | 互联网搜索（多后端） | `query`, `allowed_domains`, `blocked_domains` |
| `web_fetch` | 网页内容抓取 | `url`, `prompt` |
| `ask_user` | 向用户提问获取决策输入 | `message`, `questions` |
| `task_create` | 创建结构化任务项 | `subject`, `description` |
| `task_update` | 更新任务状态与依赖 | `taskId`, `status` |
| `start_agent` | 启动子代理（前后台模式） | `description`, `prompt` |
| `enter_plan_mode` | 进入 / 退出计划模式 | `locked`, `deactivate` |
| `create_cron` | 定时 / 周期性任务调度 | `cron`, `prompt`, `recurring` |
| `run_workflow` | 多代理工作流编排（DAG） | `script`, `name`, `scriptPath` |
| `use_skill` | 加载并执行技能模块 | `skill`, `args` |

---

## 🧪 测试

```bash
# 运行全部测试
pytest

# 指定测试模块
pytest tests/test_tools_registry.py -v

# 指定测试类
pytest tests/test_session_manager.py::TestLoad -v
```

---

## 🏗️ 架构概览

```
CLI 层 (main.py)            → argparse 命令解析
    ↓ 组装并启动
Agent 层 (agent/)            → 双循环引擎
    ↓ 调用           ↓ 使用
LLMAPI 层 (llmapi/)    Session 层 (session/)
    ↓ 调用
工具系统层 (tools/)          → BaseTool → ToolRegistry → 16 个工具
```

### 双循环架构

```
外层 while True（用户轮次）
  ├─ 接收用户输入 → messages.append()
  ├─ _run_turn()  ← 进入内层循环
  └─ turn_count += 1

内层 for _ in range(20)（LLM 工具调用循环）
  ├─ llm.think(messages, tools) → 流式响应
  ├─ "stop"       → 追加回复，退出内循环
  ├─ "tool_calls" → 执行工具 → 结果追加到 messages → 继续内循环
  └─ "error"      → 异常终止
```

详细架构文档请参阅 [ARCHITECTURE.md](./ARCHITECTURE.md)。

---

## 🔧 扩展开发

### 添加新工具

1. 在 `tools/` 下创建 `my_tool.py`，继承 `BaseTool`
2. 实现 `async execute(**kwargs) → ToolResult` 和 `get_schema() → dict`
3. 在 `tools/__init__.py` 中导出
4. 在 `main.py` 的 `create_default_registry()` 中注册

```python
from tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述"

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"result": "ok"})

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": { ... },
                    "required": [...],
                },
            },
        }
```

### 添加新技能

在 `.claude/skills/` 目录创建 `.py` 文件：

```python
name = "my-skill"
description = "我的自定义技能"

async def execute(args: str):
    return {"success": True, "data": {"output": f"处理完成: {args}"}}
```

技能自动被发现和加载，无需额外注册。

---

## 📄 许可证

本项目采用 [MIT License]() 开源。

---

## 🙏 致谢

- [Claude Code](https://claude.ai/) — 工具系统设计灵感
- [OpenAI](https://openai.com/) — Function Calling API 协议
- [prompt-toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) — 终端交互框架
- [Pydantic](https://github.com/pydantic/pydantic) — 数据模型校验
