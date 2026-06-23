"""计划模式工具 — 状态标记 + Agent 集成拦截点。

使用方式：
    # 进入计划模式
    import tools.enter_plan_mode as plan_mod
    plan_mod.activate()

    # 检查是否处于计划模式
    if plan_mod.is_active():
        ...

    # 退出计划模式
    plan_mod.deactivate()
"""

from typing import Any, Dict

from .base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# 模块级状态
# ---------------------------------------------------------------------------

_plan_mode_active: bool = False
"""全局计划模式标志。Agent 在执行破坏性操作前应检查此标志。"""

_plan_mode_lock: bool = False
"""计划模式锁定 — 一旦计划被批准，锁定防止意外退出。"""


def is_active() -> bool:
    """检查当前是否处于计划模式。"""
    return _plan_mode_active


def is_locked() -> bool:
    """检查计划模式是否已锁定（计划已批准）。"""
    return _plan_mode_lock


def activate() -> Dict[str, Any]:
    """激活计划模式。

    Returns:
        包含计划模式指引的字典。
    """
    global _plan_mode_active
    _plan_mode_active = True
    return {
        "mode": "plan",
        "status": "activated",
        "instructions": (
            "已进入计划模式。在此模式下：\n"
            "1. 全面探索代码库以理解现有架构\n"
            "2. 设计实现方案并考虑架构权衡\n"
            "3. 将方案写入计划文件供用户审查\n"
            "4. 用户批准后再开始实现\n"
            "5. 用户批准后调用 enter_plan_mode(locked=true) 锁定"
        ),
    }


def deactivate() -> Dict[str, Any]:
    """退出计划模式。

    Returns:
        包含退出信息的字典。
    """
    global _plan_mode_active, _plan_mode_lock
    if _plan_mode_lock:
        return {
            "mode": "plan",
            "status": "locked",
            "error": "计划模式已锁定，无法退出。请先完成已批准的计划。",
        }
    _plan_mode_active = False
    _plan_mode_lock = False
    return {
        "mode": "normal",
        "status": "deactivated",
        "message": "已退出计划模式，恢复到正常交互模式。",
    }


def lock() -> Dict[str, Any]:
    """锁定计划模式（用户批准计划后）。"""
    global _plan_mode_lock
    _plan_mode_lock = True
    return {
        "mode": "plan",
        "status": "locked",
        "message": "计划已锁定 — 允许执行破坏性操作。完成实现后自动退出计划模式。",
    }


def reset() -> None:
    """重置计划模式状态（主要用于测试清理）。"""
    global _plan_mode_active, _plan_mode_lock
    _plan_mode_active = False
    _plan_mode_lock = False


# ---------------------------------------------------------------------------
# EnterPlanModeTool
# ---------------------------------------------------------------------------

class EnterPlanModeTool(BaseTool):
    name = "enter_plan_mode"
    description = (
        "进入计划模式以设计实现方案，在编写代码前获得用户对方案的认可。"
        "在计划模式下，write_file / edit_file / run_bash 等破坏性工具会被限制。"
        "用户通过 locked=true 参数批准计划后可解锁这些限制。"
    )

    async def execute(self, **kwargs) -> ToolResult:
        locked = kwargs.get("locked", False)
        deactivate_flag = kwargs.get("deactivate", False)

        # ── 退出计划模式 ──
        if deactivate_flag:
            result = deactivate()
            if result.get("error"):
                return ToolResult(
                    success=False,
                    error=result["error"],
                    data=result,
                )
            return ToolResult(
                success=True,
                data=result,
                metadata={"plan_mode_active": False, "plan_mode_locked": False},
            )

        # ── 锁定（用户批准计划） ──
        if locked:
            result = lock()
            return ToolResult(
                success=True,
                data=result,
                metadata={"plan_mode_active": True, "plan_mode_locked": True},
            )

        # ── 进入计划模式 ──
        result = activate()
        return ToolResult(
            success=True,
            data=result,
            metadata={"plan_mode_active": True, "plan_mode_locked": False},
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
                        "locked": {
                            "type": "boolean",
                            "description": "用户已批准计划，锁定计划模式允许执行破坏性操作",
                            "default": False,
                        },
                        "deactivate": {
                            "type": "boolean",
                            "description": "退出计划模式（仅在未锁定时有效）",
                            "default": False,
                        },
                    },
                },
            },
        }
