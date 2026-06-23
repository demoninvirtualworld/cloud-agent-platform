"""启动子代理工具 — 复用 Agent 引擎执行独立子任务。

子代理与父代理共享 ToolRegistry，以独立 Agent 实例运行。
支持前台（等待结果）和后台（asyncio.Task）两种模式。
"""

import asyncio
import io
import sys
from contextlib import redirect_stdout
from typing import Any, Dict, Optional

from .base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# 后台任务追踪
# ---------------------------------------------------------------------------

_background_tasks: Dict[str, asyncio.Task] = {}
"""后台子代理任务追踪表。key 为描述，value 为 asyncio.Task。"""


def _make_subagent_name(description: str) -> str:
    """为子代理生成名称。"""
    short = description.strip()[:30]
    return f"SubAgent({short})" if short else "SubAgent"


async def _run_subagent(
    prompt: str,
    description: str,
    tool_registry: Any,
    model: Optional[str] = None,
    effort: str = "high",
) -> str:
    """
    创建子代理并执行一次性任务。

    Args:
        prompt: 子代理任务说明
        description: 简短描述
        tool_registry: 共享的工具注册表
        model: 模型 ID（None 则使用默认配置）
        effort: 思考力度

    Returns:
        LLM 最终回复文本
    """
    from agent.agent import Agent

    # 创建子代理实例
    agent = Agent(
        name=_make_subagent_name(description),
        max_turns=10,
        tool_registry=tool_registry,
        effort=effort,
    )

    # 替换模型（如果指定了不同模型）
    if model:
        try:
            agent.llm.model = model
        except Exception:
            pass

    # 注入任务 prompt 作为首条用户消息
    agent.messages.append({"role": "user", "content": prompt})

    # 执行内循环并捕获输出
    output_buffer = io.StringIO()
    try:
        with redirect_stdout(output_buffer):
            await agent._run_turn()
    except Exception:
        pass

    # 提取最终 assistant 回复
    final_response = ""
    for msg in reversed(agent.messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final_response = msg["content"]
            break

    if not final_response:
        final_response = output_buffer.getvalue().strip() or "(子代理未返回文本回复)"

    return final_response


# ---------------------------------------------------------------------------
# StartAgentTool
# ---------------------------------------------------------------------------

class StartAgentTool(BaseTool):
    name = "start_agent"
    description = (
        "启动一个新的子代理来执行独立任务。"
        "子代理共享当前的工具集，可以作为独立 LLM 实例完成任务。"
    )

    # 子代理最大执行超时（秒）
    SUBAGENT_TIMEOUT = 120

    async def execute(self, **kwargs) -> ToolResult:
        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        subagent_type = kwargs.get("subagent_type", "general-purpose")
        model = kwargs.get("model", None)
        run_in_background = kwargs.get("run_in_background", False)

        if not prompt and not description:
            return ToolResult(
                success=False,
                error="缺少必要参数: prompt 或 description 至少需要一个",
            )

        task_prompt = prompt or description
        task_desc = description or prompt[:50]

        # 获取当前工具注册表（优先使用全局活跃实例）
        from .registry import ToolRegistry
        active = ToolRegistry.get_active()
        tool_registry = active if active is not None else ToolRegistry()

        # ── 后台模式 ──
        if run_in_background:
            task = asyncio.create_task(
                _run_subagent(task_prompt, task_desc, tool_registry, model)
            )
            _background_tasks[task_desc] = task

            # 添加完成回调以自动清理
            def _cleanup(t: asyncio.Task) -> None:
                _background_tasks.pop(task_desc, None)

            task.add_done_callback(_cleanup)

            return ToolResult(
                success=True,
                data={
                    "description": task_desc,
                    "subagent_type": subagent_type,
                    "model": model,
                    "background": True,
                    "status": "running",
                },
            )

        # ── 前台模式（等待完成） ──
        try:
            result = await asyncio.wait_for(
                _run_subagent(task_prompt, task_desc, tool_registry, model),
                timeout=self.SUBAGENT_TIMEOUT,
            )
            return ToolResult(
                success=True,
                data={
                    "description": task_desc,
                    "subagent_type": subagent_type,
                    "model": model,
                    "background": False,
                    "status": "completed",
                    "response": result,
                },
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=(
                    f"子代理执行超时 ({self.SUBAGENT_TIMEOUT}s): {task_desc}"
                ),
            )

    @staticmethod
    def list_background_tasks() -> Dict[str, str]:
        """列出所有后台运行的子代理任务。"""
        return {
            name: "running" if not task.done() else "completed"
            for name, task in _background_tasks.items()
        }

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "子代理任务的简短描述（3-5 词）",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "子代理要执行的任务说明",
                        },
                        "subagent_type": {
                            "type": "string",
                            "description": "子代理类型，如 'general-purpose', 'Explore', 'Plan' 等",
                            "default": "general-purpose",
                        },
                        "model": {
                            "type": "string",
                            "enum": ["sonnet", "opus", "haiku"],
                            "description": "子代理使用的模型",
                        },
                        "run_in_background": {
                            "type": "boolean",
                            "description": "是否在后台运行子代理",
                            "default": False,
                        },
                    },
                    "required": ["description", "prompt"],
                },
            },
        }
