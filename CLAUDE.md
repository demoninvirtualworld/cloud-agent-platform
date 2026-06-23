# CLAUDE.md — DScode (Cloud Agent Platform)

> AI Agent 工具框架的开发指南。本文档帮助 Claude 和其他 AI 助手理解项目结构、约定和开发方式。

---

## 1. 项目身份

**DScode**（Cloud Agent Platform）是一个基于 Python 的 AI Agent 工具框架，对标 Claude Code 工具系统设计。

- **语言**: Python >= 3.10
- **版本**: 0.1.0（早期搭建阶段）
- **许可**: MIT
- **入口**: `main.py` → `python main.py` 或 `DScode`（pip install -e . 后）

核心能力：交互式 CLI 对话代理 + LLM Function Calling 工具编排 + 会话 JSON 持久化。

---

## 2. 目录结构与模块职责

```
cloud agent platform/
├── main.py                  # ★ CLI 入口 — argparse 子命令 + 命令分发
├── pyproject.toml           # 项目元数据 [project.scripts] DScode = "main:main"
├── config.py                # 从 config.json 加载 LLM 配置
├── config.json              # LLM 配置（不提交 git）
├── requirements.txt         # 锁定的 pip 依赖
│
├── agent/                   # ★ Agent 核心引擎
│   └── agent.py             #   Agent 类：双层循环（外层 REPL + 内层 Tool Calling）
│
├── llmapi/                  # ★ LLM 接口层
│   └── LLMAPI.py            #   LLMAPI 类：OpenAI 兼容客户端 + 流式响应 + 推理链
│
├── tools/                   # ★ 工具系统（16 个工具 + 注册表）
│   ├── base.py              #   BaseTool(ABC) + ToolResult(dataclass)
│   ├── registry.py          #   ToolRegistry：register/get/list/get_all_schemas
│   ├── read_file.py         #   ✅ 完整
│   ├── write_file.py        #   ✅ 完整
│   ├── edit_file.py         #   ✅ 完整
│   ├── run_bash.py          #   ✅ 完整（异步子进程）
│   ├── glob_search.py       #   ✅ 完整
│   ├── grep_search.py       #   ✅ 完整
│   ├── web_fetch.py         #   ✅ 完整
│   ├── web_search.py        #   ✅ DuckDuckGo + SerpAPI + Brave 多后端
│   ├── ask_user.py          #   ✅ 交互式问答（单选/多选/自由输入）
│   ├── task_create.py       #   ✅ 内存存储 + 辅助查询
│   ├── task_update.py       #   ✅ 状态转换校验 + 依赖追踪
│   ├── start_agent.py       #   ✅ 复用 Agent 类生成子代理
│   ├── use_skill.py         #   ✅ 技能注册表 + .claude/skills/ 加载
│   ├── enter_plan_mode.py   #   ✅ 模块级状态 + Agent 拦截
│   ├── create_cron.py       #   ✅ asyncio 调度器 + Cron 表达式解析
│   └── run_workflow.py      #   ✅ DAG 拓扑排序 + 并行子代理编排
│
├── session/                 # ★ 会话管理
│   ├── models.py            #   Message + Session（Pydantic BaseModel）
│   └── manager.py           #   SessionManager：CRUD → memory/sessions/<id>.json
│
├── ui/                      # 终端 UI
│   ├── input_handler.py     #   prompt-toolkit 输入封装（Tab 补全、多行）
│   └── completer.py         #   自动补全器
│
├── tests/                   # 测试套件（pytest + pytest-asyncio）
│   ├── conftest.py          #   具体工具桩 + fixtures
│   ├── test_tools_base.py
│   ├── test_tools_registry.py
│   ├── test_session_models.py
│   └── test_session_manager.py
│
├── memory/sessions/         # 会话持久化目录（gitignore，运行时生成）
├── 架构.md                  # 详细中文架构文档
└── 项目说明.md              # 中文项目说明
```

---

## 3. 核心架构

### 3.1 分层架构

```
CLI 层 (main.py)            → argparse 命令解析
    ↓ 组装并启动
Agent 层 (agent/)            → 双层循环引擎
    ↓ 调用           ↓ 使用
LLMAPI 层 (llmapi/)    Session 层 (session/)
    ↓ 调用
工具系统层 (tools/)          → BaseTool → ToolRegistry → 16 个工具
```

### 3.2 Agent 双层循环（关键设计）

```
外层 while True（用户轮次）
  ├─ 接收用户输入 → self.messages.append({"role": "user", ...})
  ├─ self._run_turn()
  └─ turn_count += 1

内层 for _ in range(INNER_LOOP_LIMIT=20)（LLM 轮次）
  ├─ llm.think(messages, tools, effort) → 流式响应
  ├─ stop    → 追加 assistant 消息，退出内循环
  ├─ error   → 打印错误，退出
  ├─ length  → 输出截断警告，退出
  └─ tool_calls → 逐条执行工具 → 结果追加到 messages → continue 内循环
```

- `self.messages` 归属 Agent，跨越内外循环保留完整历史
- System prompt 根据已注册工具动态生成（`_init_system_prompt()`）
- 每个工具结果序列化为 JSON 字符串（兼容 OpenAI tool role 消息格式）

### 3.3 关键数据结构

**ToolResult**（`tools/base.py`）:
```python
@dataclass
class ToolResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
```

**Message**（`session/models.py`）:
```python
class Message(BaseModel):
    role: str          # "system" | "user" | "assistant" | "tool"
    content: Optional[str]
    tool_calls: Optional[List[Dict[str, Any]]]
    tool_call_id: Optional[str]
    name: Optional[str]
    reasoning_content: Optional[str]
```

**LLMAPI.think() 返回值**:
```python
{
    "finish_reason": str,           # "stop" | "tool_calls" | "error" | "length"
    "content": Optional[str],
    "reasoning_content": Optional[str],
    "tool_calls": Optional[List[dict]],
    "error": Optional[str],         # 仅 finish_reason="error"
}
```

---

## 4. 常用命令

### 4.1 环境安装

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -e .               # 安装项目 + 依赖（开发模式）
pip install -e ".[dev]"        # 安装项目 + 开发依赖
```

### 4.2 运行

```bash
python main.py                 # 启动交互式对话（默认）
python main.py create --name my-agent --effort high --max-turns 100
python main.py list            # 列出所有会话
python main.py resume --id <id>
python main.py delete --id <id>
python main.py version
```

安装后可直接使用：`DScode`、`DScode create`、`DScode list` 等。

### 4.3 测试

```bash
pytest                                    # 全部测试
pytest tests/test_tools_registry.py -v    # 指定模块
pytest tests/test_session_manager.py::TestLoad -v  # 指定测试类
```

---

## 5. 扩展开发规范

### 5.1 添加新工具

1. 在 `tools/` 下创建 `my_tool.py`
2. 继承 `BaseTool`，设置 `name` 和 `description`
3. 实现 `async execute(**kwargs) → ToolResult`
4. 实现 `get_schema() → dict`（返回 OpenAI function calling JSON Schema）
5. 在 `tools/__init__.py` 中导出类
6. 在 `main.py` 的 `create_default_registry()` 中 `registry.register(MyTool())`

工具 Schema 格式：
```python
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

### 5.2 配置

- 配置文件：项目根目录 `config.json`（从 `config.json.example` 复制）
- 由 `config.py` 加载，LLMAPI 初始化时自动读取
- 支持任意 OpenAI 兼容接口（DeepSeek、OpenAI、Ollama 等）

---

## 6. 技术栈

| 分类 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.10+ | 主语言 |
| LLM SDK | openai >= 2.0 | API 调用 |
| HTTP | httpx >= 0.28 | HTTP 请求 |
| 数据模型 | pydantic >= 2.0 | Session / Message |
| CLI UI | prompt-toolkit >= 3.0 | 交互式输入 |
| 测试 | pytest >= 9.0 + pytest-asyncio | 单元测试 |
| 配置 | JSON（config.json） | 运行时配置 |

---

## 7. 开发注意事项

- **Windows 兼容**: `main.py` 启动时会调用 `_setup_encoding()` 将 stdout/stderr 重配置为 UTF-8，避免 GBK 乱码
- **异步优先**: 所有工具 `execute()` 方法均为 async，Agent 入口通过 `asyncio.run()` 调用
- **工具安全**: `RunBashTool` 使用 `asyncio.create_subprocess_shell`，需注意命令注入风险
- **内循环上限**: `INNER_LOOP_LIMIT = 20`，防止 LLM 无限循环调用工具
- **会话存储**: 每个会话独立 JSON 文件存储在 `memory/sessions/<id>.json`，ID 使用 `uuid4().hex[:12]`
- **流式累积**: LLMAPI 按 index 聚合流式返回的 tool_calls delta，自动推断 finish_reason
- **编码风格**: 所有源文件使用 UTF-8，文档字符串为中文，类型注解使用 `Optional` / `List` / `Dict` 等（兼容 Python 3.10）
- **计划模式**: `enter_plan_mode` 激活后，Agent 拦截 `write_file`/`edit_file`/`run_bash`，需用户 `locked=true` 批准才解锁
- **子代理共享**: `start_agent` 通过 `ToolRegistry.set_active()` / `get_active()` 与父代理共享工具集
- **技能目录**: `.claude/skills/*.py` 存放技能模块，需提供 `name`、`description`、`async execute(args)` 接口
- **工作流目录**: `.claude/workflows/*.py` 或 `.json` 存放预定义工作流

---

## 8. 当前项目状态

- **已完成**: 全部 16 个工具实现完毕 ✅
  - 核心文件工具：read_file、write_file、edit_file、run_bash、glob_search、grep_search、web_fetch
  - 搜索工具：web_search（DuckDuckGo + SerpAPI + Brave 多后端）
  - 交互工具：ask_user（结构化问题 + 单选/多选/自由输入）
  - 任务管理：task_create、task_update（内存存储 + 依赖追踪 + 状态转换校验）
  - 计划模式：enter_plan_mode（模块级状态 + Agent 破坏性操作拦截）
  - 子代理：start_agent（复用 Agent 实例 + 前台/后台模式）
  - 技能系统：use_skill（SkillRegistry + .claude/skills/ 动态加载 + 内置 code-review/verify）
  - 定时任务：create_cron（asyncio 调度器 + CronParser 5字段解析）
  - 工作流：run_workflow（DAG 拓扑排序 + 并行子代理编排 + 断点续传）
- **Agent 集成**：计划模式拦截 write_file/edit_file/run_bash、全局 ToolRegistry 共享
- **测试覆盖**: 104 个测试全部通过
