# DScode 架构详解

> 基于 Python 的 AI Agent 工具框架 — 从主循环到工具调用再到各模块实现的完整技术文档

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [架构总览](#3-架构总览)
4. [启动流程：从命令行到 Agent 实例化](#4-启动流程从命令行到-agent-实例化)
5. [核心引擎：双循环架构](#5-核心引擎双循环架构)
6. [LLM 客户端：流式调用与 Function Calling](#6-llm-客户端流式调用与-function-calling)
7. [工具系统](#7-工具系统)
8. [会话管理](#8-会话管理)
9. [终端 UI 系统](#9-终端-ui-系统)
10. [配置管理](#10-配置管理)
11. [计划模式](#11-计划模式)
12. [子代理与工作流](#12-子代理与工作流)
13. [定时任务调度](#13-定时任务调度)
14. [技能系统](#14-技能系统)
15. [扩展指南](#15-扩展指南)

---

## 1. 项目概述

DScode 是一个基于 Python 3.10+ 构建的 **AI Agent 工具框架**，对标 Claude Code 的工具系统设计。它让大语言模型（LLM）能够通过 **Function Calling** 机制主动调用各类工具（文件读写、代码搜索、Shell 执行、网页抓取等），在交互式终端中完成复杂的编程与问题求解任务。

**核心数据流**：

```
用户输入 → Agent 编排 → LLM 推理 → 工具调用请求 → 本地执行工具 → 结果回传 LLM → LLM 生成最终回复 → 输出给用户
```

---

## 2. 技术栈

| 层次 | 技术选型 | 用途 |
|------|---------|------|
| **语言** | Python 3.10+ | 异步原生支持（`async`/`await`） |
| **LLM SDK** | `openai` ≥ 2.0 | 兼容 OpenAI 协议的 API 调用（DeepSeek / OpenAI / Ollama 等） |
| **HTTP 客户端** | `httpx` ≥ 0.28 | 异步 HTTP 请求（网页抓取、搜索 API） |
| **数据模型** | `pydantic` ≥ 2.0 | 会话/消息序列化与类型校验 |
| **终端 UI** | `prompt-toolkit` ≥ 3.0 | 带语法高亮、自动补全、键位绑定的交互式输入 |
| **异步运行时** | `asyncio`（标准库） | 子进程管理、超时控制、并发工具执行 |
| **配置** | JSON（`config.json`） | LLM 密钥、模型、搜索后端等配置 |
| **测试** | `pytest` + `pytest-asyncio` | 异步单元测试 |
| **安装** | `setuptools` + `pip install -e .` | 可编辑安装（Editable Install） |

---

## 3. 架构总览

```
DScode/
├── main.py                     # CLI 入口（argparse 子命令 + 工具注册工厂）
├── config.py                   # 配置加载（从 config.json 读取 LLM 等设置）
├── agent/
│   └── agent.py                # Agent 核心 — 内外双循环编排引擎
├── llmapi/
│   └── LLMAPI.py               # LLM 客户端 — 流式响应解析 + Function Calling
├── tools/                      # 工具系统（16 个工具）
│   ├── base.py                 #   BaseTool 抽象基类 + ToolResult 统一返回
│   ├── registry.py             #   ToolRegistry 注册表（存取/枚举/全局单例）
│   ├── read_file.py            #   读取文件（分页 + 行号）
│   ├── write_file.py           #   写入文件（覆盖 / 创建）
│   ├── edit_file.py            #   精确字符串替换（单次 / 全部）
│   ├── run_bash.py             #   异步 Shell 命令执行
│   ├── glob_search.py          #   Glob 模式文件搜索
│   ├── grep_search.py          #   正则表达式内容搜索（3 种输出模式）
│   ├── web_search.py           #   互联网搜索（DuckDuckGo / SerpAPI / Brave）
│   ├── web_fetch.py            #   网页内容抓取
│   ├── ask_user.py             #   向用户提问获取决策输入
│   ├── task_create.py          #   创建结构化任务项（内存存储）
│   ├── task_update.py          #   更新任务状态 + 依赖追踪
│   ├── start_agent.py          #   启动子代理（共享工具集，前后台模式）
│   ├── enter_plan_mode.py      #   计划模式（限制破坏性工具，需审批解锁）
│   ├── create_cron.py          #   定时任务调度（cron 表达式 + asyncio）
│   ├── run_workflow.py         #   多代理工作流编排（DAG 拓扑排序）
│   └── use_skill.py            #   技能加载与执行（.claude/skills/ 目录）
├── session/                    # 会话持久化
│   ├── models.py               #   Pydantic 数据模型（Message / Session）
│   └── manager.py              #   SessionManager CRUD（JSON 文件存储）
├── ui/                         # 终端交互界面
│   ├── input_handler.py        #   美化输入处理器（prompt_toolkit / fallback input）
│   └── completer.py            #   Tab 自动补全（/ 命令 + @ 文件路径）
├── pyproject.toml              # 项目元数据与依赖声明
└── requirements.txt            # 锁定依赖版本
```

---

## 4. 启动流程：从命令行到 Agent 实例化

### 4.1 CLI 入口（`main.py`）

DScode 的入口是 `main:main` 函数。当用户在终端输入 `DScode` 时，`pip install -e .` 安装时生成的 wrapper 脚本会调用它。

```python
# pyproject.toml
[project.scripts]
DScode = "main:main"
```

启动流程分为三个阶段：

**阶段一：参数解析**

```
DScode [无参数]          → 默认创建新会话（name="DScode", max_turns=50, effort="high"）
DScode create [选项]     → 创建指定配置的新会话
DScode list              → 列出所有已保存会话
DScode resume --id <ID>  → 恢复历史会话
DScode delete --id <ID>  → 删除指定会话
DScode version           → 显示版本信息
```

**阶段二：环境检查**

```python
# config.py → check_llm_config()
# 检查 config.json 中是否存在必要字段：
#   llm.model_id, llm.api_key, llm.base_url
# 任一缺失则打印错误并退出
```

**阶段三：工具注册与 Agent 构建**

```python
# main.py → create_default_registry()
registry = ToolRegistry()
registry.register(ReadFileTool())      # 读取文件
registry.register(WriteFileTool())     # 写入文件
registry.register(EditFileTool())      # 编辑文件
registry.register(RunBashTool())       # Shell 命令
registry.register(GlobSearchTool())    # 文件搜索
registry.register(GrepSearchTool())    # 内容搜索
registry.register(WebSearchTool())     # 网络搜索
registry.register(WebFetchTool())      # 网页抓取
registry.register(StartAgentTool())    # 子代理
registry.register(AskUserTool())       # 用户提问
registry.register(TaskCreateTool())    # 任务创建
registry.register(TaskUpdateTool())    # 任务更新
registry.register(UseSkillTool())      # 技能调用
registry.register(EnterPlanModeTool()) # 计划模式
registry.register(CreateCronTool())    # 定时任务
registry.register(RunWorkflowTool())   # 工作流

# 构建 Agent 实例
agent = Agent(
    name="DScode",
    max_turns=50,
    tool_registry=registry,
    effort="high",
)
asyncio.run(agent.run())  # 进入异步事件循环
```

### 4.2 Agent 初始化

在 `Agent.__init__()` 中完成以下初始化：

1. **LLM 客户端**：实例化 `LLMAPI()`，从 `config.json` 自动加载 API 配置
2. **工具注册表**：设置为全局活跃实例（`ToolRegistry.set_active()`），供子代理共享
3. **输入会话**：实例化 `InputSession()`，封装 prompt_toolkit 的美化输入
4. **系统提示词**：根据已注册工具动态生成 System Prompt，注入到 `self.messages[0]`

```python
# agent/agent.py → _init_system_prompt()
system_text = (
    "You are an AI agent — an intelligent assistant designed to "
    "help users solve problems by reasoning, planning, and using "
    "available tools.\n\n"
    "## Available Tools\n\n"
    f"{tool_descriptions}\n\n"     # ← 自动列出所有已注册工具
    "## Instructions\n\n"
    "- Analyze the user's request carefully before acting.\n"
    "- Use tools when needed to gather information or take action.\n"
    ...
)
```

---

## 5. 核心引擎：双循环架构

这是 DScode 最核心的设计 —— **外层 REPL 循环 + 内层 Tool Calling 循环**。

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent.run() — 外层循环                     │
│                                                             │
│  while turn_count < max_turns:                              │
│      query = await input_session.prompt()   ← 等待用户输入    │
│      self.messages.append({"role":"user", "content":query}) │
│      await self._run_turn()                ← 进入内层循环    │
│      turn_count += 1                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               Agent._run_turn() — 内层循环                    │
│                                                             │
│  for _ in range(INNER_LOOP_LIMIT=20):                       │
│      result = llm.think(messages, tools)  ← 调用 LLM        │
│                                                             │
│      if finish_reason == "stop":                            │
│          写入 assistant 回复到 messages                      │
│          break  ← 退出内循环，返回外层等待下一轮用户输入        │
│                                                             │
│      if finish_reason == "tool_calls":                      │
│          写入 assistant 消息（含 tool_calls）到 messages      │
│          for tc in tool_calls:                              │
│              result = await tool.execute(args)              │
│              写入 tool 结果到 messages                       │
│          continue  ← 继续内循环，LLM 消化工具结果              │
│                                                             │
│      if finish_reason in ("error", "length"):               │
│          break  ← 异常终止                                   │
└─────────────────────────────────────────────────────────────┘
```

### 5.1 为什么需要双循环？

这是与 Function Calling 协议紧密配合的设计：

- **外层循环**：对应对话的"轮次"（Turn），每轮以一次用户输入开始
- **内层循环**：对应单轮中 LLM 可能发起的**连续多次工具调用**

以实际场景为例：

```
[外层第1轮]
  You: "帮我分析项目结构"
  → [内层循环开始]
    ① LLM 返回 tool_calls: [glob_search(**/*)]
       Agent 执行 → 追加 tool 结果到 messages
    ② LLM 消化结果，返回 tool_calls: [read_file(main.py)]
       Agent 执行 → 追加 tool 结果
    ③ LLM 消化结果，返回 tool_calls: [read_file(agent.py)]
       Agent 执行 → 追加 tool 结果
    ④ LLM 消化结果，finish_reason="stop"，给出分析总结
  → [内层循环结束]

[外层第2轮]
  You: "解释一下双循环的设计"
  → [内层循环开始]
    ① LLM 返回 finish_reason="stop"（无需工具即可回答）
  → [内层循环结束]
```

### 5.2 安全保护

- **内循环上限**：`INNER_LOOP_LIMIT = 20`，防止 LLM 陷入无限工具调用循环
- **轮次上限**：`max_turns`（默认 50），防止无限对话
- **计划模式拦截**：在内循环中，若处于未锁定的计划模式，`write_file`、`edit_file`、`run_bash` 会被拒绝

### 5.3 messages 的生命周期

`self.messages` 是一个 `List[Dict[str, Any]]`，归属于 Agent 实例，**跨越内、外层循环持久保留**：

```
messages = [
    {"role": "system",   "content": "You are an AI agent..."},          # 0: 系统提示词
    {"role": "user",     "content": "帮我分析项目结构"},                   # 1: 用户输入（外层追加）
    {"role": "assistant","content": None, "tool_calls": [...]},          # 2: LLM 工具调用（内层追加）
    {"role": "tool",     "tool_call_id": "xxx", "content": "{...}"},     # 3: 工具结果（内层追加）
    {"role": "assistant","content": None, "tool_calls": [...]},          # 4: 第二次工具调用
    {"role": "tool",     "tool_call_id": "yyy", "content": "{...}"},     # 5: 工具结果
    {"role": "assistant","content": "项目结构分析如下..."},                # 6: LLM 最终回复（内层追加）
    {"role": "user",     "content": "解释双循环"},                        # 7: 下一轮用户输入（外层追加）
    ...
]
```

这种设计确保了 LLM 在每次调用时都能看到完整的对话上下文（包括之前所有的工具调用和结果），这是 Function Calling 协议的核心要求。

---

## 6. LLM 客户端：流式调用与 Function Calling

`llmapi/LLMAPI.py` 是对 OpenAI SDK 的封装，核心方法只有一个：**`think()`**。

### 6.1 初始化

```python
class LLMAPI:
    def __init__(self, model=None, apiKey=None, baseUrl=None, timeout=None):
        llm_config = get_llm_config()  # 从 config.json 加载
        self.model = model or llm_config["model_id"]
        self.client = OpenAI(
            api_key=apiKey or llm_config["api_key"],
            base_url=baseUrl or llm_config["base_url"],
            timeout=timeout or llm_config["timeout"],
        )
```

支持任何 OpenAI 兼容接口（DeepSeek、OpenAI、Ollama、vLLM 等），只需在 `config.json` 中配置正确的 `base_url`。

### 6.2 think() 方法

```python
def think(self, messages, temperature=0, tools=None, effort=None) -> dict:
    """
    Returns:
        {
            "finish_reason": str,       # "stop" | "tool_calls" | "length" | "error"
            "content": Optional[str],   # 文本回复
            "reasoning_content": Optional[str],  # 推理链（extended thinking 模型）
            "tool_calls": Optional[List[dict]],  # 工具调用列表
        }
    """
```

### 6.3 流式响应处理

LLM 使用 **Server-Sent Events（SSE）流式返回**，需要处理三个并发的增量流：

```
for chunk in response:                    # 每个 SSE chunk
    delta = chunk.choices[0].delta

    if delta.content:
        collected_content += delta.content     # ① 文本增量
        print(delta.content, end="", flush=True)  # 实时打印

    if delta.reasoning_content:
        collected_reasoning += delta.reasoning_content  # ② 推理链增量（DeepSeek）

    if delta.tool_calls:
        for tc in delta.tool_calls:
            # ③ 工具调用增量 → 按 index 聚合
            tool_calls_accumulator[tc.index] = {
                "id": tc.id,
                "function": {
                    "name":  accumulated_name,
                    "arguments": accumulated_json_fragments,
                }
            }
```

**关键点**：工具调用参数在流式传输中是**分片到达**的 JSON 片段，需要按 `index` 做增量拼接，最终得到完整的 JSON 参数字符串。

### 6.4 Extended Thinking 支持

对于支持推理链的模型（如 DeepSeek），通过 `extra_body` 参数启用：

```python
if effort:
    request_kwargs["extra_body"] = {
        "thinking": {"type": "enabled", "effort": effort}
    }
```

`effort` 可选值为 `"low"`、`"medium"`、`"high"`，控制模型在推理时的思考深度。

---

## 7. 工具系统

### 7.1 基类与统一返回

```python
# tools/base.py

@dataclass
class ToolResult:
    success: bool                       # 执行是否成功
    data: Optional[Any] = None          # 成功时返回的数据
    error: Optional[str] = None         # 失败时的错误信息
    metadata: Dict[str, Any] = {}       # 附加元数据

class BaseTool(ABC):
    name: str = ""                      # 工具唯一名称
    description: str = ""               # 工具描述（会出现在 System Prompt 中）

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult: ...

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]: ...
```

**设计要点**：

- 所有工具**异步执行**（`async def execute`），避免阻塞事件循环
- `get_schema()` 返回 **OpenAI Function Calling JSON Schema** 格式，直接传给 LLM
- `ToolResult` 使用 `@dataclass`，序列化为 JSON 后传给 LLM 作为 `tool` 角色的消息内容

### 7.2 注册表（ToolRegistry）

```python
# tools/registry.py

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}  # name → tool 实例

    def register(self, tool: BaseTool)    # 注册工具
    def get(self, name: str) -> BaseTool  # 按名称获取
    def list_tools(self) -> List[dict]    # 返回 [{name, description}, ...]
    def get_all_schemas(self) -> List[dict]  # 返回所有工具的 JSON Schema
    def set_active(self)                  # 设为全局活跃实例（供子代理使用）
```

**全局活跃注册表**：通过模块级变量 `_active_registry` 实现单例模式。子代理通过 `ToolRegistry.get_active()` 获取父代理的注册表，实现**工具集共享**。

### 7.3 工具调用流程（在 Agent 中）

```python
# agent/agent.py → _execute_tool()

async def _execute_tool(self, tool_name, tool_args) -> str:
    tool = self.tool_registry.get(tool_name)
    if tool is None:
        return json.dumps({"success": False, "error": "工具未注册"})

    # 计划模式拦截
    if is_active() and not is_locked() and tool_name in _PLAN_RESTRICTED_TOOLS:
        return json.dumps({"success": False, "error": "计划模式下该工具被限制"})

    result = await tool.execute(**tool_args)
    return json.dumps({
        "success": result.success,
        "data": result.data,
        "error": result.error,
    }, ensure_ascii=False, default=str)
```

工具执行结果被序列化为 JSON 字符串，以 `{"role": "tool", "content": "..."}` 的形式追加到 messages 中回传给 LLM。

### 7.4 核心工具详解

#### 7.4.1 read_file — 读取文件

- **参数**：`file_path`（必填）、`offset`（起始行，从 0 开始）、`limit`（最大行数，默认 2000）
- **实现**：读取文件全部行 → 按 offset/limit 截取 → 带行号格式化输出
- **编码处理**：使用 `errors="replace"` 容错，捕获 `UnicodeDecodeError`

#### 7.4.2 write_file — 写入文件

- **参数**：`file_path`（必填）、`content`（必填）
- **实现**：`path.parent.mkdir(parents=True, exist_ok=True)` → 创建父目录 → 写入内容
- **返回**：写入字节数、字符数

#### 7.4.3 edit_file — 精确字符串替换

- **参数**：`file_path`、`old_string`、`new_string`、`replace_all`（默认 False）
- **单次替换模式**：要求 `old_string` 在文件中**只出现一次**，否则报错
- **全部替换模式**（`replace_all=True`）：替换所有匹配
- **安全保护**：替换前检查匹配次数，替换后检查内容是否确实发生变化

#### 7.4.4 run_bash — Shell 命令执行

- **参数**：`command`（必填）、`timeout`（默认 120000ms，最大 600000ms）、`workdir`
- **实现**：使用 `asyncio.create_subprocess_shell()` 异步创建子进程
- **超时处理**：`asyncio.wait_for(proc.communicate(), timeout=timeout_sec)`，超时则 `proc.kill()`
- **输出限制**：stdout/stderr 各截取前 100,000 字符

#### 7.4.5 glob_search — Glob 文件搜索

- **参数**：`pattern`（必填）、`path`（默认 `.`）
- **实现**：支持 `**` 递归匹配，自动去重，最多返回 500 条结果

#### 7.4.6 grep_search — 正则内容搜索

- **参数**：`pattern`（必填，正则）、`path`、`glob`（文件过滤）、`output_mode`、`case_insensitive`、`multiline`、`context`（上下文行数）、`head_limit`
- **三种输出模式**：
  - `files_with_matches`：返回匹配到的文件路径列表
  - `content`：返回匹配的具体行及文本
  - `count`：仅返回匹配总数统计
- **默认文本扩展名过滤**：自动跳过非文本文件（二进制等）

#### 7.4.7 web_search — 互联网搜索

- **多后端架构**：通过 `_resolve_backend()` 工厂函数选择后端
- **DuckDuckGo**（默认，免费）：Instant Answer API + HTML 回退双路径
- **SerpAPI**：需 API Key，解析 `organic_results`
- **Brave Search**：需 API Key，调用 Brave Search API
- **域名过滤**：支持 `allowed_domains` 白名单和 `blocked_domains` 黑名单

#### 7.4.8 web_fetch — 网页抓取

- **参数**：`url`（必填）、`prompt`（可选处理提示）
- **安全限制**：仅支持 HTTP/HTTPS，最大响应 5MB，超时 30s
- **内容类型**：仅处理 `text/html`、`text/plain`、`application/json`

#### 7.4.9 ask_user — 用户提问

- **参数**：`message`（文本消息）、`questions`（结构化问题列表）
- **结构化问题**：支持选项列表（`options`）、多选（`multiSelect`）、标签（`header`）
- **交互流程**：在终端打印问题 → 等待用户输入 → 收集答案 → 返回结构化结果

#### 7.4.10 task_create / task_update — 任务管理

- **存储**：进程级内存字典 `_task_store: Dict[str, Dict]`
- **task_create**：生成 8 位短 UUID，创建任务记录（status=pending）
- **task_update**：状态机管理 + 依赖追踪
  - 合法状态转换：`pending → in_progress → completed`（支持回退和删除）
  - 依赖关系：通过 `addBlocks` 和 `addBlockedBy` 建立任务间的阻塞/被阻塞关系（双向关联）

---

## 8. 会话管理

### 8.1 数据模型（`session/models.py`）

```python
class Message(BaseModel):
    role: str                                    # system | user | assistant | tool
    content: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None      # assistant 消息的工具调用
    tool_call_id: Optional[str] = None           # tool 消息的调用 ID
    name: Optional[str] = None
    reasoning_content: Optional[str] = None      # 推理链内容

class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])  # 12 位短 ID
    name: str = "Unnamed Session"
    agent_name: str = "default"
    messages: List[Message] = []
    turn_count: int = 0
    max_turns: int = 50
    created_at: str       # ISO 8601
    updated_at: str

    def to_api_messages(self) -> List[Dict]:
        """将内部消息转换为 LLM API 格式（跳过 system 消息）"""
```

### 8.2 SessionManager（`session/manager.py`）

- **存储位置**：`memory/sessions/<id>.json`（每个会话一个 JSON 文件）
- **CRUD 操作**：`create()`、`save()`、`load()`、`delete()`、`list_sessions()`、`session_exists()`
- **安全性**：session ID 经过清理（仅保留字母数字和 `-`），防止路径穿越
- **列表排序**：按文件修改时间倒序（最近活跃的会话在前）

### 8.3 会话恢复流程

```python
# main.py → cmd_resume()
session = manager.load(args.id)                          # 1. 加载 JSON
restored_messages = session.to_api_messages()            # 2. 转换为 API 格式
agent.messages = [agent.messages[0]] + restored_messages # 3. 保留 system prompt + 历史消息
agent.turn_count = session.turn_count                    # 4. 恢复轮数
asyncio.run(agent.run())                                 # 5. 启动（从断点继续）
```

**关键设计**：`to_api_messages()` 故意跳过 `role="system"` 的消息，因为 system prompt 由 Agent 在初始化时根据**当前注册的工具**动态生成。这样即使工具集发生变化，恢复的会话也能正常工作。

---

## 9. 终端 UI 系统

### 9.1 InputSession（`ui/input_handler.py`）

双模式输入处理器：

**增强模式**（prompt_toolkit 可用时）：
- 带样式的输入框（绿色 `>` 提示符、白色文本）
- 装饰线：输入框上方和下方各有 `─` 装饰线
- 键位绑定：`Ctrl+D` 退出、`Alt+Enter` 换行
- 内建命令历史（`InMemoryHistory`）
- 实时补全（`complete_while_typing=True`）

**回退模式**（非 TTY 环境 / CI / Git Bash 下）：
- 自动降级为内置 `input("> ")`
- 保证在所有终端环境下都能正常工作

### 9.2 ChatCompleter（`ui/completer.py`）

自定义补全器，根据输入前缀自动切换：

- **`/` 前缀** → 补全内置命令：`/exit`、`/quit`、`/help`、`/clear`、`/save`、`/version`
- **`@` 前缀** → 补全文件系统路径（相对当前工作目录），显示文件大小和类型（目录/文件）

---

## 10. 配置管理

### 10.1 config.json 结构

```json
{
    "llm": {
        "model_id": "deepseek-v4-pro",
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

### 10.2 config.py 加载机制

```python
_PROJECT_ROOT = Path(__file__).resolve().parent  # 始终指向项目根目录
_CONFIG_PATH = _PROJECT_ROOT / "config.json"

def load_config() -> dict:       # 加载完整配置
def get_llm_config() -> dict:    # 提取 LLM 配置段
def check_llm_config() -> str:   # 验证必要字段完整性
```

**设计要点**：使用 `Path(__file__).resolve().parent` 而非 `os.getcwd()`，确保无论从哪个目录运行 `DScode`，都能**正确定位项目根目录**下的 `config.json`。

---

## 11. 计划模式

计划模式（Plan Mode）是一个**安全机制**，在编写代码前限制破坏性操作。

### 11.1 状态模型

```python
# tools/enter_plan_mode.py

_plan_mode_active: bool = False   # 是否处于计划模式
_plan_mode_lock: bool = False     # 是否已锁定（用户已批准计划）
```

三种状态：

| `_plan_mode_active` | `_plan_mode_lock` | 含义 | 破坏性工具 |
|---------------------|-------------------|------|-----------|
| `False` | `False` | 正常模式 | 允许 |
| `True` | `False` | 计划模式（审查中） | **拒绝** |
| `True` | `True` | 计划模式（已批准） | 允许 |

### 11.2 拦截点

在 `Agent._execute_tool()` 中：

```python
_PLAN_RESTRICTED_TOOLS = {"write_file", "edit_file", "run_bash"}

if is_active() and not is_locked() and tool_name in _PLAN_RESTRICTED_TOOLS:
    return json.dumps({"success": False, "error": "当前处于计划模式，工具被限制..."})
```

### 11.3 典型使用流程

```
LLM: enter_plan_mode()                  → 进入计划模式（_plan_mode_active=True）
LLM: 探索代码库，设计实现方案，写入计划文件
LLM: ask_user("请审查上述方案")           → 向用户展示计划
User: 批准
LLM: enter_plan_mode(locked=true)       → 锁定计划模式（_plan_mode_lock=True）
LLM: write_file / edit_file / run_bash  → 现在允许执行破坏性操作
LLM: enter_plan_mode(deactivate=true)   → 退出计划模式
```

---

## 12. 子代理与工作流

### 12.1 start_agent — 子代理

```python
# tools/start_agent.py

async def _run_subagent(prompt, description, tool_registry, model, effort):
    agent = Agent(name=..., max_turns=10, tool_registry=tool_registry, effort=effort)
    agent.messages.append({"role": "user", "content": prompt})
    output_buffer = io.StringIO()
    with redirect_stdout(output_buffer):
        await agent._run_turn()  # 复用 Agent 的内循环
    # 提取最终 assistant 回复
    return final_response
```

**关键设计**：

1. **复用 Agent 引擎**：子代理就是独立的 `Agent` 实例，共享父代理的 `ToolRegistry`
2. **输出捕获**：使用 `redirect_stdout` 将子代理的工具调用日志重定向到缓冲区，避免污染父代理的终端输出
3. **双模式**：
   - **前台模式**（默认）：等待子代理完成，返回结果。超时 120s
   - **后台模式**（`run_in_background=True`）：以 `asyncio.Task` 启动，立即返回。通过 `list_background_tasks()` 查询状态

### 12.2 run_workflow — 多代理工作流编排

工作流定义格式（支持 JSON 和 Python-like）：

```json
[
    {"agent": "Explorer",   "prompt": "搜索所有 Python 文件", "depends_on": []},
    {"agent": "Analyzer",   "prompt": "分析 $args.target",    "depends_on": [0]},
    {"agent": "Reporter",   "prompt": "生成报告",            "depends_on": [0, 1]}
]
```

**核心引擎**：`WorkflowEngine` 使用 **DAG 拓扑排序** 确定执行顺序：

```
步骤 0: in_degree=0 ─┐
                      ├→ 第0层（并行执行步骤0）
步骤 1: depends=[0] ─┤
                      │
步骤 2: depends=[0,1] → 第1层（等待步骤0和1完成后再执行）
```

- **同层并行**：同一层内的步骤通过 `asyncio.gather()` 并行执行
- **依赖失败传播**：若依赖步骤失败，后续步骤自动跳过
- **变量替换**：`$args.xxx` 语法支持参数化工作流
- **超时控制**：每个步骤 180s，整体工作流 600s

### 12.3 工作流定义来源

```python
# 三种来源
run_workflow(script='[{"agent":"...","prompt":"..."}]')     # ① 内联脚本
run_workflow(name="my_workflow")                            # ② .claude/workflows/my_workflow.py
run_workflow(scriptPath="/path/to/workflow.json")           # ③ 外部文件
```

---

## 13. 定时任务调度

### 13.1 CronParser — Cron 表达式解析器

支持标准 5 字段 cron 表达式（分 时 日 月 周）：

```python
"*/5 * * * *"     → 每 5 分钟
"0 9 * * 1-5"     → 工作日早上 9 点
"0 0 1,15 * *"    → 每月 1 号和 15 号午夜
```

**`next_after(dt)` 方法**：从给定时间开始，逐分钟递增搜索下一次匹配，上限 365 天。

### 13.2 CronScheduler — 调度引擎

- 每个 job 以独立的 `asyncio.Task` 运行
- 主循环：计算下次触发时间 → `await asyncio.sleep(wait_seconds)` → 触发回调
- 支持一次性任务（`recurring=False`，执行后自动停止）
- 通过全局单例 `get_scheduler()` 共享调度器

---

## 14. 技能系统

技能（Skill）是存放在 `.claude/skills/` 目录下的 Python 模块，支持**热加载和动态扩展**。

### 14.1 技能模块规范

```python
# .claude/skills/my_skill.py

name = "my-skill"
description = "我的自定义技能"

async def execute(args: str) -> ToolResult:
    # 技能逻辑
    return ToolResult(success=True, data={"result": "done"})
```

### 14.2 SkillRegistry — 技能注册表

- **懒加载**：首次调用 `get()` 或 `list_skills()` 时才扫描目录
- **动态加载**：使用 `importlib.util.spec_from_file_location()` 动态加载 `.py` 文件
- **内置回退**：当 `.claude/skills/` 目录不存在时，自动注册两个内置技能：
  - `code-review`：扫描 Python 文件，检查 bare except、文件过长等常见问题
  - `verify`：运行 `pytest` 测试套件

### 14.3 执行适配

```python
result = self._execute_fn(args)
if asyncio.iscoroutine(result):   # 自动检测是否需要 await
    result = await result
```

同时支持**同步**和**异步**技能函数，自动适配。

---

## 15. 扩展指南

### 15.1 添加新工具

1. 在 `tools/` 目录创建 `my_tool.py`：

```python
from .base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述（会出现在 System Prompt 和 LLM 的工具列表中）"

    async def execute(self, **kwargs) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, data={"key": "value"})

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

2. 在 `main.py` 的 `create_default_registry()` 中注册：

```python
from tools.my_tool import MyTool
registry.register(MyTool())
```

3. 无需重新安装（editable install），直接运行即可生效。

### 15.2 添加新技能

在 `.claude/skills/` 目录创建 `.py` 文件：

```python
name = "my-skill"
description = "我的自定义技能"

async def execute(args: str):
    # 技能逻辑
    return {"success": True, "data": {"output": f"处理完成: {args}"}}
```

技能自动被 `SkillRegistry` 发现和加载，无需额外注册。

### 15.3 添加预定义工作流

在 `.claude/workflows/` 目录创建 `.json` 或 `.py` 文件：

```json
[
    {"agent": "Step 1", "prompt": "执行第一步", "depends_on": []},
    {"agent": "Step 2", "prompt": "执行第二步", "depends_on": [0]},
    {"agent": "Step 3", "prompt": "执行第三步", "depends_on": [0, 1]}
]
```

通过 `run_workflow(name="my_workflow")` 调用。

---

## 附录 A：关键设计决策

| 决策 | 理由 |
|------|------|
| **Editable Install（`pip install -e .`）** | 开发时修改代码立即生效，无需反复重装 |
| **双循环架构** | 匹配 Function Calling 协议：外层走对话轮次，内层走工具调用链 |
| **异步工具执行** | 避免阻塞事件循环，支持并发工具调用（如工作流并行步骤） |
| **全局 ToolRegistry** | 子代理共享父代理工具集，避免重复实例化 |
| **Pydantic 会话模型** | 类型安全 + JSON 自动序列化/反序列化 |
| **prompt_toolkit + fallback** | 保证在各种终端环境下都能使用（包括 CI/Git Bash） |
| **流式输出即时打印** | 边接收边显示，用户感知延迟更低 |
| **计划模式状态机** | 模块级全局变量实现零侵入的破坏性操作拦截 |
| **DAG 拓扑排序工作流** | 支持复杂任务依赖，同层自动并行 |

## 附录 B：异步架构图

```
asyncio.run(agent.run())
│
├── InputSession.prompt()           ← asyncio.to_thread() 包装同步阻塞输入
│
├── LLMAPI.think()                  ← 异步 HTTP SSE 流式调用
│   └── openai.chat.completions.create(stream=True)
│
├── Tool.execute()                  ← 异步工具执行
│   ├── RunBashTool: asyncio.create_subprocess_shell()
│   ├── WebFetchTool: httpx.AsyncClient.get()
│   ├── WebSearchTool: httpx.AsyncClient.get()
│   └── 其他工具: async def execute()
│
├── StartAgentTool._run_subagent()  ← 异步子代理执行
│   └── agent._run_turn() → llm.think() → tool.execute()
│
├── WorkflowEngine.execute()        ← asyncio.gather() 并行执行步骤
│
└── CronScheduler._run_job()        ← asyncio.sleep() + callback
```
