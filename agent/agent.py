"""Agent 核心 — 对话代理，负责编排 LLM 与工具的交互。"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from llmapi.LLMAPI import LLMAPI
from tools.registry import ToolRegistry


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
        name: str = "cap-agent",
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

            try:
                query = (await asyncio.to_thread(input, "\nYou: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n会话已中断。")
                break

            if not query:
                continue

            if query.lower() in ("exit", "quit"):
                print("再见！")
                break

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

                    tool_result_str = await self._execute_tool(tool_name, tool_args)

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

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """查找工具并执行，将 ToolResult 序列化为 JSON 字符串返回。"""
        tool = self.tool_registry.get(tool_name)

        if tool is None:
            return json.dumps(
                {"success": False, "error": f"工具 '{tool_name}' 未注册。"},
                ensure_ascii=False,
                default=str,
            )

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

    def _print_welcome(self) -> None:
        """打印启动信息。"""
        tool_count = len(self.tool_registry.list_tools())
        print(f"\n{self.name} 代理启动！")
        print(f"   工具数量: {tool_count}")
        print(f"   最大轮数: {self.max_turns}")
        print(f"   思考力度: {self.effort}")
        print("\n输入 'exit' 或 'quit' 退出对话。")
        print("-" * 50)
