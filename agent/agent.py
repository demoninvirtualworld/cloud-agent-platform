"""Agent 核心 — 对话代理，负责编排 LLM 与工具的交互。"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

from llmapi.LLMAPI import LLMAPI
from tools.registry import ToolRegistry
from ui.input_handler import InputSession
from ui.spinner import Spinner


class Agent:
    """
    对话代理 — 管理一次交互式会话的完整生命周期。

    外层 while 循环持续接收用户输入，内层循环处理单轮中 LLM
    的连续工具调用，直到 finish_reason="stop" 才进入下一轮。
    messages 归属于 Agent，跨内外循环保留完整对话历史。

    整体以 async 驱动，入口通过 asyncio.run(agent.run()) 调用。
    """

    INNER_LOOP_LIMIT = 20  # 内循环安全上限，防止无限工具调用

    def __init__(
        self,
        name: str = "DScode",
        max_turns: int = 50,
        tool_registry: Optional[ToolRegistry] = None,
        effort: str = "high",
    ):
        self.name = name
        self.max_turns = max_turns
        self.tool_registry = tool_registry or ToolRegistry()
        self.llm = LLMAPI()
        self.effort = effort
        self.turn_count = 0

        # 设为全局活跃注册表（供子代理等使用）
        self.tool_registry.set_active()

        # 美化的终端输入
        self._input_session = InputSession()

        # messages 归属于 Agent，跨越内外循环保留完整对话历史
        self.messages: List[Dict[str, Any]] = []
        self._init_system_prompt()

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """启动交互式 REPL。外层死循环，直到退出或达到最大轮数。"""
        self._print_welcome()

        while True:
            if self.turn_count >= self.max_turns:
                print(f"\n已达到最大对话轮数 ({self.max_turns})，会话结束。")
                break

            # 重置顶部装饰线（每轮输入前）
            self._input_session.reset_deco()

            try:
                query = await asyncio.to_thread(self._input_session.prompt)
            except (EOFError, KeyboardInterrupt):
                print("\n\n会话已中断。")
                break

            if query is None:
                # Ctrl+D 退出
                print("\n\n会话已中断。")
                break

            query = query.strip()

            if not query:
                continue

            # 处理内置命令（以 / 开头）
            if query.startswith("/"):
                result = await self._handle_command(query)
                if result == "continue":
                    continue
                elif result == "exit":
                    break
                # result 为 None：不是已知命令，当作普通文本发送给 LLM

            # 用户消息加入历史
            self.messages.append({"role": "user", "content": query})

            # 进入内层循环：处理 LLM 响应 & 工具调用
            await self._run_turn()

            self.turn_count += 1

    # ------------------------------------------------------------------
    # 内循环：单轮 LLM 对话
    # ------------------------------------------------------------------

    async def _run_turn(self) -> None:
        """
        内层循环：持续调用 LLM，若返回 tool_calls 则执行工具并将
        结果追加到 messages，然后继续；若 finish_reason="stop" 则
        退出内循环，messages 保留供下一轮使用。
        """
        tool_schemas = (
            self.tool_registry.get_all_schemas()
            if self.tool_registry.list_tools()
            else None
        )

        for _ in range(self.INNER_LOOP_LIMIT):
            result = self.llm.think(
                messages=self.messages,
                tools=tool_schemas,
                effort=self.effort,
            )

            finish_reason = result.get("finish_reason")

            # --- stop: LLM 给出最终回复，退出内循环 ---
            if finish_reason == "stop":
                content = result.get("content")
                reasoning = result.get("reasoning_content")
                if content:
                    msg: Dict[str, Any] = {"role": "assistant", "content": content}
                    if reasoning:
                        msg["reasoning_content"] = reasoning
                    self.messages.append(msg)
                break

            # --- error / length: 异常终止 ---
            if finish_reason in ("error", "length"):
                if finish_reason == "error":
                    print(f"\nLLM 调用失败: {result.get('error')}")
                else:
                    print("\nLLM 响应被截断 (finish_reason=length)")
                break

            # --- tool_calls: 执行工具，结果追加到 messages，继续内循环 ---
            tool_calls = result.get("tool_calls")
            if tool_calls:
                # 将 assistant 消息（含 tool_calls）写入历史
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": result.get("content"),
                    "tool_calls": tool_calls,
                }
                reasoning = result.get("reasoning_content")
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                self.messages.append(assistant_msg)

                # 逐条执行工具调用
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_call_id = tc["id"]

                    try:
                        tool_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    self._print_tool_before(tool_name, tool_args)

                    tool_spinner = Spinner(f"执行 {tool_name}...")
                    tool_spinner.start()
                    tool_result_str = await self._execute_tool(tool_name, tool_args)
                    tool_spinner.stop(silent=True)

                    self._print_tool_after(tool_name, tool_args, tool_result_str)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result_str,
                    })

                continue  # 回到内循环，让 LLM 消化工具结果

            # 无内容无工具调用 —— 异常情况，安全退出
            break

    # ------------------------------------------------------------------
    # 工具执行
    # ------------------------------------------------------------------

    # 计划模式下受限的工具
    _PLAN_RESTRICTED_TOOLS = {"write_file", "edit_file", "run_bash"}

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """查找工具并执行，将 ToolResult 序列化为 JSON 字符串返回。"""
        tool = self.tool_registry.get(tool_name)

        if tool is None:
            return json.dumps(
                {"success": False, "error": f"工具 '{tool_name}' 未注册。"},
                ensure_ascii=False,
                default=str,
            )

        # ── 计划模式拦截 ──
        try:
            from tools.enter_plan_mode import is_active, is_locked
            if (
                is_active()
                and not is_locked()
                and tool_name in self._PLAN_RESTRICTED_TOOLS
            ):
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            f"当前处于计划模式，工具 '{tool_name}' 被限制。"
                            "请先让用户审查方案，批准后调用 enter_plan_mode(locked=true) 解锁。"
                        ),
                    },
                    ensure_ascii=False,
                )
        except Exception:
            pass  # 如果模块加载失败，不阻止执行

        try:
            result = await tool.execute(**tool_args)
            return json.dumps(
                {
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                },
                ensure_ascii=False,
                default=str,
            )
        except Exception as exc:
            return json.dumps(
                {"success": False, "error": f"工具执行异常: {exc}"},
                ensure_ascii=False,
                default=str,
            )

    # ------------------------------------------------------------------
    # 工具调用日志
    # ------------------------------------------------------------------

    def _print_tool_before(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """打印工具调用前的操作描述。"""
        desc = self._tool_action_desc(tool_name, tool_args)
        if desc:
            print(f"\n🔧 {tool_name} → {desc}")

    def _print_tool_after(self, tool_name: str, tool_args: Dict[str, Any], result_str: str) -> None:
        """打印工具调用后的结果摘要（成功/失败 + 关键指标）。"""
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            return

        if result.get("success"):
            metrics = self._tool_success_metrics(tool_name, result.get("data", {}))
            print(f"   ✅ 成功{metrics}")
        else:
            error = result.get("error", "未知错误")
            print(f"   ❌ 失败: {error}")

    def _tool_action_desc(self, tool_name: str, args: Dict[str, Any]) -> str:
        """根据工具类型和参数生成操作描述。"""
        if tool_name == "read_file":
            return f"读取 {args.get('file_path', '?')}"
        if tool_name == "write_file":
            size = len(args.get("content", ""))
            return f"写入 {args.get('file_path', '?')} ({size} 字符)"
        if tool_name == "edit_file":
            return f"编辑 {args.get('file_path', '?')}"
        if tool_name == "run_bash":
            cmd = args.get("command", "?")
            return f"执行 {cmd[:60]}{'...' if len(cmd) > 60 else ''}"
        if tool_name == "glob_search":
            return f"搜索 {args.get('pattern', '?')}"
        if tool_name == "grep_search":
            return f"搜索 \"{args.get('pattern', '?')}\""
        if tool_name == "web_fetch":
            return f"获取 {args.get('url', '?')}"
        if tool_name == "web_search":
            return f"搜索 \"{args.get('query', '?')}\""
        if tool_name == "start_agent":
            return f"启动子代理: {args.get('description', '?')}"
        if tool_name == "task_create":
            return f"创建任务: {args.get('subject', '?')}"
        if tool_name == "task_update":
            status = args.get("status", "")
            return f"更新任务 {args.get('taskId', '?')}{f' → {status}' if status else ''}"
        return ""

    def _tool_success_metrics(self, tool_name: str, data: Dict[str, Any]) -> str:
        """从 ToolResult.data 中提取关键指标。"""
        if tool_name == "read_file":
            total = data.get("total_lines", 0)
            start = data.get("start_line", 0)
            end = data.get("end_line", 0)
            return f" — 读取第 {start}-{end} 行 (共 {total} 行)"
        if tool_name == "write_file":
            return f" — 写入 {data.get('bytes_written', '?')} 字节"
        if tool_name == "edit_file":
            return f" — {data.get('replacements', '?')} 处替换"
        if tool_name == "run_bash":
            return f" — 退出码 {data.get('exit_code', '?')}"
        if tool_name == "glob_search":
            return f" — 匹配 {data.get('match_count', 0)} 个文件"
        if tool_name == "grep_search":
            files = len(data.get("files_with_matches", []))
            total = data.get("total_matches", 0)
            return f" — {files} 个文件, {total} 处匹配"
        if tool_name == "web_fetch":
            return f" — {data.get('content_length', '?')} 字符, HTTP {data.get('status_code', '?')}"
        if tool_name == "web_search":
            return f" — {len(data.get('results', []))} 条结果"
        if tool_name == "task_create":
            return f" — ID: {data.get('task_id', '?')}"
        return ""

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _init_system_prompt(self) -> None:
        """根据已注册的工具列表生成 system prompt 并写入 messages。"""
        tools = self.tool_registry.list_tools()
        if not tools:
            system_text = (
                "You are an AI agent. Help the user with their tasks. "
                "No tools are currently available."
            )
        else:
            tool_descriptions = "\n".join(
                f"- **{t['name']}**: {t['description']}" for t in tools
            )
            system_text = (
                "You are an AI agent — an intelligent assistant designed to "
                "help users solve problems by reasoning, planning, and using "
                "available tools.\n\n"
                "## Available Tools\n\n"
                f"{tool_descriptions}\n\n"
                "## Instructions\n\n"
                "- Analyze the user's request carefully before acting.\n"
                "- Use tools when needed to gather information or take action.\n"
                "- Call tools with correct and complete parameters.\n"
                "- After each tool call, wait for the result before proceeding.\n"
                "- Return a clear, helpful final response to the user.\n"
                "- If a tool fails, explain the error and suggest alternatives.\n"
            )

        self.messages.append({"role": "system", "content": system_text})

    # ------------------------------------------------------------------
    # 内置命令处理
    # ------------------------------------------------------------------

    async def _handle_command(self, text: str) -> Optional[str]:
        """
        处理以 / 开头的内容命令。

        Returns:
            "exit"     — 退出循环
            "continue" — 已处理，继续循环
            None       — 不是已知命令，作为普通文本处理（发送给 LLM）
        """
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            print("再见！")
            return "exit"

        if cmd == "/help":
            self._print_command_help()
            return "continue"

        if cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            return "continue"

        if cmd == "/save":
            await self._save_session()
            return "continue"

        if cmd == "/version":
            from main import VERSION
            print(f"\nDScode v{VERSION}")
            print(f"Python {sys.version}")
            print(f"工具数量: {len(self.tool_registry.list_tools())}")
            return "continue"

        # 未知命令 — 不作为命令处理，发送给 LLM
        return None

    def _print_command_help(self) -> None:
        """打印内置命令帮助。"""
        help_text = """
内置命令:
  /exit, /quit    退出对话
  /help           显示此帮助信息
  /clear          清屏
  /save           保存当前会话
  /version        显示版本信息

提示:
  @文件名   — 使用 Tab 键自动补全文件路径
  /命令     — 使用 Tab 键自动补全命令
  Alt+Enter — 输入换行
  Ctrl+D    — 退出
"""
        print(help_text)

    async def _save_session(self) -> None:
        """保存当前会话到 JSON 文件。"""
        try:
            from session.manager import SessionManager
            from session.models import Session, Message

            manager = SessionManager()
            # 将内部 dict 格式消息转换为 Message 模型
            msg_objects = []
            for m in self.messages:
                msg_objects.append(Message(
                    role=m.get("role", ""),
                    content=m.get("content"),
                    tool_calls=m.get("tool_calls"),
                    tool_call_id=m.get("tool_call_id"),
                    name=m.get("name"),
                    reasoning_content=m.get("reasoning_content"),
                ))
            session = Session(
                agent_name=self.name,
                max_turns=self.max_turns,
                messages=msg_objects,
                turn_count=self.turn_count,
            )
            manager.save(session)
            print(f"\n✅ 会话已保存: {session.id}")
        except Exception as e:
            print(f"\n❌ 保存失败: {e}")

    def _print_welcome(self) -> None:
        """打印启动信息。"""
        tool_count = len(self.tool_registry.list_tools())
        print(f"\n{self.name} 代理启动！")
        print(f"   工具数量: {tool_count}")
        print(f"   最大轮数: {self.max_turns}")
        print(f"   思考力度: {self.effort}")
        print("\n输入 /help 查看可用命令，Tab 键自动补全。")
        self._input_session.reset_deco()
