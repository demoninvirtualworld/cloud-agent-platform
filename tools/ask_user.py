"""询问用户工具 — 向用户提问以获取决策输入。"""

import asyncio
import sys
from typing import Any, Dict

from .base import BaseTool, ToolResult


class AskUserTool(BaseTool):
    name = "ask_user"
    description = "向用户提问以获取决策输入或确认操作"

    async def execute(self, **kwargs) -> ToolResult:
        questions = kwargs.get("questions", [])
        message = kwargs.get("message", "")

        if not questions and not message:
            return ToolResult(
                success=False,
                error="缺少必要参数: questions 或 message 至少需要一个",
            )

        # 如果有 message，直接显示
        if message:
            print(f"\n❓ {message}")

        # 如果有结构化问题，逐个展示
        answers: Dict[str, Any] = {}
        if questions:
            for i, q in enumerate(questions, start=1):
                if isinstance(q, dict):
                    question_text = q.get("question", "")
                    header = q.get("header", f"Q{i}")
                    options = q.get("options", [])
                    multi_select = q.get("multiSelect", False)

                    print(f"\n{'─' * 50}")
                    print(f"📋 [{header}] {question_text}")

                    if options:
                        for j, opt in enumerate(options, start=1):
                            label = opt.get("label", opt) if isinstance(opt, dict) else opt
                            desc = opt.get("description", "") if isinstance(opt, dict) else ""
                            print(f"  {j}. {label}")
                            if desc:
                                print(f"     {desc}")

                        sel_type = "（可多选，逗号分隔）" if multi_select else ""
                        print(f"\n请输入选择{sel_type}: ", end="")
                    else:
                        print("\n请输入: ", end="")

                    try:
                        user_input = (await asyncio.to_thread(input)).strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\n⚠️ 用户取消输入")
                        return ToolResult(
                            success=False,
                            error="用户取消了输入",
                        )

                    if options and user_input:
                        selected_indices = [
                            int(x.strip()) - 1
                            for x in user_input.split(",")
                            if x.strip().isdigit()
                        ]
                        selected = [
                            options[idx]
                            for idx in selected_indices
                            if 0 <= idx < len(options)
                        ]
                        answers[header] = selected if multi_select else (selected[0] if selected else None)
                    else:
                        answers[header] = user_input
                else:
                    print(f"\n❓ {q}")
                    try:
                        answers[f"q{i}"] = (await asyncio.to_thread(input, "> ")).strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\n⚠️ 用户取消输入")
                        return ToolResult(
                            success=False,
                            error="用户取消了输入",
                        )

        return ToolResult(
            success=True,
            data={
                "message": message,
                "questions": questions,
                "answers": answers,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "要显示给用户的消息",
                        },
                        "questions": {
                            "type": "array",
                            "description": "结构化问题列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "type": "string",
                                        "description": "问题内容",
                                    },
                                    "header": {
                                        "type": "string",
                                        "description": "问题简短标签（最多 12 字符）",
                                    },
                                    "options": {
                                        "type": "array",
                                        "description": "可选项列表",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "description": {"type": "string"},
                                            },
                                        },
                                    },
                                    "multiSelect": {
                                        "type": "boolean",
                                        "description": "是否允许多选",
                                        "default": False,
                                    },
                                },
                                "required": ["question", "header"],
                            },
                        },
                    },
                    "required": [],
                },
            },
        }
