# DScode

基于 Python 的 AI Agent 工具框架，对标 Claude Code 工具系统设计。支持 LLM 对话、工具调用（Function Calling）、会话持久化，提供交互式命令行界面。

## 架构概览

```
DScode/
├── agent/                  # Agent 核心 — 对话编排层
│   └── agent.py            #   外层 REPL + 内层 Tool Calling 循环
├── tools/                  # 工具系统 — 16 个可扩展工具
│   ├── base.py             #   BaseTool 抽象基类 + ToolResult 统一返回
│   ├── registry.py         #   ToolRegistry 注册表（注册/查找/枚举/清空）
│   └── *.py                #   具体工具实现
├── session/                # 会话管理 — 持久化与恢复
│   ├── models.py           #   Pydantic 数据模型（Message / Session）
│   └── manager.py          #   SessionManager CRUD 操作
├── llmapi/                 # LLM 客户端 — OpenAI 兼容接口
│   └── LLMAPI.py           #   流式响应、工具调用、推理链支持
├── config.py               # 配置管理 — 从 config.json 加载
├── tests/                  # 单元测试 — 覆盖核心模块
├── memory/sessions/        # 会话持久化存储（JSON 文件）
├── main.py                 # CLI 入口（argparse 子命令）
├── pyproject.toml          # 项目元数据与依赖
└── requirements.txt        # 锁定的依赖版本
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

## 可用工具

| 工具 | 状态 | 说明 |
|------|------|------|
| `read_file` | ✅ 完整 | 读取文件内容，支持分页和行范围 |
| `write_file` | ✅ 完整 | 写入内容到指定文件 |
| `edit_file` | ✅ 完整 | 精确字符串替换编辑（单次/全部） |
| `run_bash` | ✅ 完整 | 执行 Shell 命令，支持超时控制 |
| `glob_search` | ✅ 完整 | Glob 模式匹配搜索文件 |
| `grep_search` | ✅ 完整 | 正则表达式内容搜索（3 种输出模式） |
| `web_fetch` | ✅ 完整 | 获取 URL 内容（HTTP/HTTPS） |
| `web_search` | ⚠️ 骨架 | 网络搜索（待对接搜索引擎 API） |
| `ask_user` | ✅ 完整 | 向用户提问获取决策输入 |
| `task_create` | ✅ 完整 | 创建结构化任务项 |
| `task_update` | ✅ 完整 | 更新任务状态与信息 |
| `start_agent` | ⚠️ 骨架 | 启动子代理（待 Agent Runtime 实现） |
| `use_skill` | ⚠️ 骨架 | 调用技能命令 |
| `enter_plan_mode` | ⚠️ 骨架 | 进入计划模式 |
| `create_cron` | ⚠️ 骨架 | 创建定时任务 |
| `run_workflow` | ⚠️ 骨架 | 执行多代理工作流 |

## 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行全部测试
pytest

# 运行指定测试模块
pytest tests/test_tools_registry.py -v

# 运行单个测试类
pytest tests/test_session_manager.py::TestLoad -v
```

## 扩展开发

### 添加新工具

1. 在 `tools/` 目录创建 `my_tool.py`
2. 继承 `BaseTool`，实现 `execute()` 和 `get_schema()`
3. 在 `tools/__init__.py` 中导出
4. 在 `main.py` 的 `create_default_registry()` 中注册

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

## 项目状态

当前处于 **早期搭建阶段**。工具系统骨架已完成，核心工具（文件操作、搜索、命令执行）可正常使用。上层 Agent Runtime、子代理编排、工作流引擎等模块仍在开发中。

## 技术栈

- **语言**：Python 3.10+
- **LLM**：OpenAI SDK（兼容接口）
- **HTTP**：httpx
- **数据模型**：Pydantic
- **配置**：JSON（config.json）
- **测试**：pytest + pytest-asyncio

## License

MIT
