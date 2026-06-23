"""共享测试设施 — 具体工具桩与 pytest fixtures。"""

from typing import Any, Dict

import pytest

from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from session.models import Message, Session


# ── 具体工具桩（用于测试 BaseTool + ToolRegistry）─────────────────────

class SimpleTool(BaseTool):
    """总是成功的具体工具。"""
    name = "simple_tool"
    description = "A simple test tool"

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=kwargs.get("input", None))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"input": {"type": "string"}},
        }


class FailingTool(BaseTool):
    """总是失败的具体工具。"""
    name = "failing_tool"
    description = "A tool that always fails"

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=False, error="Intentional failure")

    def get_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}


class EmptyNameTool(BaseTool):
    """name 为空 — 应按注册表拒绝。"""
    name = ""
    description = "This tool has no name"

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True)

    def get_schema(self) -> Dict[str, Any]:
        return {}


class IncompleteTool(BaseTool):
    """缺少 execute 抽象方法实现 — 不能实例化。"""
    name = "incomplete"
    description = "Missing execute implementation"

    def get_schema(self) -> Dict[str, Any]:
        return {}


class MissingSchemaTool(BaseTool):
    """缺少 get_schema 抽象方法实现 — 不能实例化。"""
    name = "missing_schema"
    description = "Missing get_schema implementation"

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def simple_tool():
    return SimpleTool()


@pytest.fixture
def failing_tool():
    return FailingTool()


@pytest.fixture
def empty_registry():
    return ToolRegistry()


@pytest.fixture
def populated_registry(simple_tool, failing_tool):
    registry = ToolRegistry()
    registry.register(simple_tool)
    registry.register(failing_tool)
    return registry


@pytest.fixture
def sample_message():
    return Message(role="user", content="Hello")


@pytest.fixture
def sample_session():
    return Session(name="Test Session")
