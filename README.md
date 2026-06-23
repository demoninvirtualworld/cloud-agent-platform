# DScode

基于 Python 的 AI Agent 工具框架，对标 Claude Code 工具系统设计。支持 LLM 对话、工具调用（Function Calling）、会话持久化，提供美化的交互式命令行界面。

## 架构概览

```
DScode/
├── agent/                  # Agent 核心 — 对话编排层
│   └── agent.py            #   外层 REPL + 内层 Tool Calling 循环
├── ui/                     # 终端交互界面
│   ├── input_handler.py    #   美化输入框（prompt_toolkit / 回退）
│   ├── completer.py        #   / 命令补全 + @ 文件补全
│   └── spinner.py          #   旋转计时器（长时间操作进度反馈）
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
├── tests/                  # 单元测试 — 104 个测试全覆盖
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

### 交互界面

启动后进入美化交互式对话界面：

```
DScode 代理启动！
   工具数量: 16
   最大轮数: 50
   思考力度: high

输入 /help 查看可用命令，Tab 键自动补全。

──────────────────────────────────────────────────────────────────
> 帮我分析项目结构                                     ← 绿色 > 提示符
──────────────────────────────────── Tab:补全  Ctrl+D:退出
```

**输入特性**：
- `/` + **Tab** — 弹出命令补全菜单（/help、/exit、/save、/clear、/version）
- `@` + **Tab** — 弹出文件路径补全菜单
- **Alt+Enter** — 插入换行
- **Ctrl+D** — 退出对话
- 原生 Windows 控制台（CMD / Windows Terminal）：完整的 prompt_toolkit 增强体验
- IDE 内置终端 / Git Bash：自动回退到基本模式，保证兼容性

### 内置命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/exit`, `/quit` | 退出对话 |
| `/clear` | 清屏 |
| `/save` | 保存当前会话到磁盘 |
| `/version` | 显示版本信息 |

## 系统架构

### 双层循环设计

```
┌─ 外层循环（REPL）─────────────────────────────────┐
│  while True:                                       │
│    query = await input("> ")   ← 用户输入          │
│    if query == "/exit": break                      │
│    messages.append({"role":"user", "content":...}) │
│    await _run_turn()           ← 进入内层          │
│    turn_count += 1                                 │
└────────────────────────────────────────────────────┘
         │
         ▼
┌─ 内层循环（Tool Calling）──────────────────────────┐
│  for _ in range(20):           ← 安全上限          │
│    result = llm.think(messages, tools)             │
│    if stop:  break              ← LLM 回答完毕     │
│    if tool_calls:                                    │
│      for each tool_call:                            │
│        execute_tool()           ← 执行工具          │
│        messages.append(result)  ← 结果回传          │
│      continue                   ← 继续消化          │
└────────────────────────────────────────────────────┘
```

关键设计决策：
- **messages 归属 Agent**：跨内外循环保留完整上下文，LLM 能看到所有历史工具调用
- **内循环安全上限 20**：防止工具调用无限循环
- **async 全链路**：Agent → LLM → Tool 全部异步，输入通过 `asyncio.to_thread` 桥接同步的 prompt_toolkit

### 终端适配策略

```
启动 → 检测终端类型
  ├─ GetConsoleWindow() != 0 → 增强模式
  │   └─ prompt_toolkit（补全菜单、样式化输入）
  └─ GetConsoleWindow() == 0 → 回退模式
      └─ 内置 input() + 装饰线
```

## 可用工具

| 工具 | 状态 | 说明 |
|------|------|------|
| `read_file` | ✅ 完整 | 读取文件内容，支持分页和行范围 |
| `write_file` | ✅ 完整 | 写入内容到指定文件 |
| `edit_file` | ✅ 完整 | 精确字符串替换编辑（单次/全部） |
| `run_bash` | ✅ 完整 | 跨平台 Shell 命令，自动检测 Git Bash |
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

### run_bash 跨平台支持

DScode 会自动检测系统上的 Git Bash，优先使用 bash 执行命令：

```
Windows 检测流程:
  1. 查找 bash（PATH → E:\Git → C:\Program Files\Git）
  2. 排除 WSL 存根（C:\Windows\System32\bash.exe）
  3. 验证 bash --version 可用
  4. 可用 → create_subprocess_exec(bash, "-c", cmd)
     不可用 → create_subprocess_shell(cmd)  [默认 cmd.exe]
```

工具描述会根据检测结果动态调整——bash 可用时告诉 LLM 使用 Unix 命令，不可用时提示使用 Windows 命令。

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

测试覆盖：
- `tests/test_tools_base.py` — BaseTool 抽象基类、ToolResult 数据类
- `tests/test_tools_registry.py` — ToolRegistry 注册/查找/枚举/清空
- `tests/test_session_models.py` — Message / Session Pydantic 模型
- `tests/test_session_manager.py` — SessionManager CRUD 操作

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

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 类型注解、async/await、dataclass |
| LLM | OpenAI SDK | 流式响应、Function Calling、推理链 |
| HTTP | httpx | web_fetch 工具 |
| 数据模型 | Pydantic v2 | Session / Message 序列化与校验 |
| 终端 UI | prompt_toolkit | 美化输入框、补全菜单、键位绑定 |
| 配置 | JSON (config.json) | 模型 ID、API Key、超时等 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |

## License

MIT
