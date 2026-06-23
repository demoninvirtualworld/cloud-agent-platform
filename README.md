# DScode

基于 Python 的 AI Agent 工具框架，对标 Claude Code 工具系统设计。支持 LLM 对话、工具调用（Function Calling）、会话持久化，提供交互式命令行界面。

> **版本**: 0.1.0 | **许可**: MIT | **测试**: 104 passed ✅

## 架构概览

```
DScode/
├── agent/                  # Agent 核心 — 对话编排层
│   └── agent.py            #   外层 REPL + 内层 Tool Calling 循环
├── llmapi/                 # LLM 客户端 — OpenAI 兼容接口
│   └── LLMAPI.py           #   流式响应、工具调用、推理链支持
├── tools/                  # 工具系统 — 16 个可扩展工具
│   ├── base.py             #   BaseTool 抽象基类 + ToolResult 统一返回
│   ├── registry.py         #   ToolRegistry 注册表（注册/查找/枚举/清空）
│   └── *.py                #   具体工具实现
├── session/                # 会话管理 — 持久化与恢复
│   ├── models.py           #   Pydantic 数据模型（Message / Session）
│   └── manager.py          #   SessionManager CRUD 操作
├── ui/                     # 终端 UI
│   ├── input_handler.py    #   prompt-toolkit 输入封装（Tab 补全、多行）
│   └── completer.py        #   自动补全器
├── tests/                  # 单元测试 — 104 个测试全部通过
├── memory/sessions/        # 会话持久化存储（JSON 文件）
├── main.py                 # CLI 入口（argparse 子命令）
├── config.py               # 配置管理 — 从 config.json 加载
├── config.json.example     # 配置文件模板
├── pyproject.toml          # 项目元数据与依赖
├── requirements.txt        # 锁定的依赖版本
├── CLAUDE.md               # AI 助手指南
├── ARCHITECTURE.md         # 英文架构文档
└── 架构.md                 # 中文架构文档
```

**核心流程**：用户输入 → Agent 调用 LLM → LLM 返回工具调用 → Agent 执行工具 → 结果回传 LLM → LLM 给出最终回复。

## 快速开始

### 环境要求

- Python >= 3.10
- 兼容 OpenAI 接口的 LLM 服务（如 DeepSeek、OpenAI、Ollama 等）

### 安装

```bash
# 克隆项目
git clone <your-repo-url>
cd DScode

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# 安装依赖 + 项目（安装后可在任意目录使用 DScode 命令）
pip install -e .
```

### 配置

在项目根目录创建 `config.json` 文件（或复制 `config.json.example`）：

```json
{
    "llm": {
        "model_id": "deepseek-v4-pro",
        "api_key": "your-api-key-here",
        "base_url": "https://api.deepseek.com",
        "timeout": 60
    }
}
```

| 字段 | 说明 |
|------|------|
| `llm.model_id` | 模型 ID，如 `deepseek-v4-pro`、`gpt-4o` |
| `llm.api_key` | API 密钥 |
| `llm.base_url` | API 服务地址 |
| `llm.timeout` | 请求超时秒数（默认 60） |

### 运行

```bash
# 安装后，在任意目录直接输入 DScode 即可启动（推荐）
DScode                              # 默认创建新会话
DScode create                       # 创建新会话
DScode create --name my-agent --effort high --max-turns 100
DScode list                         # 列出所有已保存会话
DScode resume --id <session-id>     # 恢复指定会话
DScode delete --id <session-id>     # 删除指定会话
DScode version                      # 显示版本信息
```

启动后会进入交互式对话界面：

```
DScode 代理启动！
   工具数量: 16
   最大轮数: 50
   思考力度: high

输入 'exit' 或 'quit' 退出对话。
--------------------------------------------------

You: 帮我分析项目结构
🧠 正在调用 deepseek-v4-pro 模型...
🔧 glob_search → 搜索 **/*
   ✅ 成功 — 匹配 45 个文件
🔧 read_file → 读取 main.py
   ✅ 成功 — 读取第 1-353 行 (共 353 行)
...
```

## 可用工具（16 个）

### 文件操作
| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容，支持分页和行范围 |
| `write_file` | 写入内容到指定文件 |
| `edit_file` | 精确字符串替换编辑（单次/全局替换） |

### 系统命令
| 工具 | 说明 |
|------|------|
| `run_bash` | 异步执行 Shell 命令，支持超时控制 |

### 搜索工具
| 工具 | 说明 |
|------|------|
| `glob_search` | Glob 模式匹配搜索文件 |
| `grep_search` | 正则表达式内容搜索（content/files/count 三种模式） |
| `web_fetch` | 获取 URL 内容并转换为 Markdown |
| `web_search` | 网络搜索（DuckDuckGo / SerpAPI / Brave 多后端） |

### 交互工具
| 工具 | 说明 |
|------|------|
| `ask_user` | 向用户提问获取决策输入（单选/多选/自由输入） |

### 任务管理
| 工具 | 说明 |
|------|------|
| `task_create` | 创建结构化任务项，支持依赖追踪 |
| `task_update` | 更新任务状态（pending→in_progress→completed），含状态转换校验 |

### 高级编排
| 工具 | 说明 |
|------|------|
| `start_agent` | 启动子代理（复用 Agent 实例，支持前台/后台模式） |
| `use_skill` | 调用技能命令（SkillRegistry + `.claude/skills/` 动态加载） |
| `enter_plan_mode` | 进入计划模式，拦截破坏性操作等待批准 |
| `create_cron` | 创建定时任务（5 字段 Cron 表达式 + asyncio 调度器） |
| `run_workflow` | 执行多代理工作流（DAG 拓扑排序 + 并行编排 + 断点续传） |

## 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行全部测试（104 个）
pytest

# 运行指定测试模块
pytest tests/test_tools_registry.py -v

# 运行单个测试类
pytest tests/test_session_manager.py::TestLoad -v
```

## 扩展开发

### 添加新工具

1. 在 `tools/` 目录创建 `my_tool.py`
2. 继承 `BaseTool`，设置 `name` 和 `description`
3. 实现 `async execute(**kwargs) → ToolResult`
4. 实现 `get_schema() → dict`（返回 OpenAI function calling JSON Schema）
5. 在 `tools/__init__.py` 中导出类
6. 在 `main.py` 的 `create_default_registry()` 中注册

```python
# tools/my_tool.py
from .base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"

    async def execute(self, **kwargs) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, data={"result": "done"})

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "参数说明"},
                    },
                    "required": ["param1"],
                },
            },
        }
```

### 核心架构要点

- **双层循环引擎**: 外层 REPL 处理用户轮次，内层循环（上限 20 次）处理 LLM Tool Calling
- **流式响应**: LLMAPI 实时流式输出，按 index 聚合 tool_calls delta
- **异步优先**: 所有工具 `execute()` 为 async，Agent 通过 `asyncio.run()` 启动
- **会话持久化**: 每个会话独立 JSON 存储在 `memory/sessions/<id>.json`

## 项目状态

| 模块 | 状态 |
|------|------|
| 核心文件工具（read/write/edit） | ✅ 完整 |
| Shell 命令执行 | ✅ 完整 |
| 搜索工具（glob/grep/web_fetch/web_search） | ✅ 完整 |
| 交互式问答（ask_user） | ✅ 完整 |
| 任务管理（create/update） | ✅ 完整 |
| 计划模式（enter_plan_mode） | ✅ 完整 |
| 子代理（start_agent） | ✅ 完整 |
| 技能系统（use_skill） | ✅ 完整 |
| 定时任务（create_cron） | ✅ 完整 |
| 工作流编排（run_workflow） | ✅ 完整 |
| Agent 双层循环引擎 | ✅ 完整 |
| LLM 接口层（流式 + 推理链） | ✅ 完整 |
| 会话持久化 | ✅ 完整 |
| 单元测试 | ✅ 104 个测试全部通过 |

## 技术栈

| 分类 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.10+ | 主语言 |
| LLM SDK | openai >= 2.0 | API 调用 |
| HTTP | httpx >= 0.28 | HTTP 请求 |
| 数据模型 | pydantic >= 2.0 | Session / Message |
| CLI UI | prompt-toolkit >= 3.0 | 交互式输入 |
| 测试 | pytest >= 9.0 + pytest-asyncio | 单元测试 |
| 配置 | JSON（config.json） | 运行时配置 |

## 相关文档

- [CLAUDE.md](CLAUDE.md) — AI 助手开发指南（含完整架构说明与开发规范）
- [ARCHITECTURE.md](ARCHITECTURE.md) — 英文架构设计文档
- [架构.md](架构.md) — 中文详细架构文档
- [DScode项目深度技术解析.md](DScode项目深度技术解析.md) — 深度技术解析

## License

MIT
