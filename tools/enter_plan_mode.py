"""进入计划模式工具。"""

from typing import Any, Dict

from .base import BaseTool, ToolResult


class EnterPlanModeTool(BaseTool):
    name = "enter_plan_mode"
    description = "进入计划模式以设计实现方案，在编写代码前获得用户对方案的认可"

    async def execute(self, **kwargs) -> ToolResult:
        # 计划模式是 Agent Runtime 级别的状态转换。
        # 当前为骨架实现 —— 上层 Agent 将处理计划模式的进入/退出逻辑。
        return ToolResult(
            success=True,
            data={
                "mode": "plan",
                "status": "entered",
                "instructions": (
                    "已进入计划模式。在此模式下：\n"
                    "1. 全面探索代码库以理解现有架构\n"
                    "2. 设计实现方案并考虑架构权衡\n"
                    "3. 将方案写入计划文件供用户审查\n"
                    "4. 用户批准后再开始实现\n"
                ),
            },
            metadata={"plan_mode_active": True},
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }
