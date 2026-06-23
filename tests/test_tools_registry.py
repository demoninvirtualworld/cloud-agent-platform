"""测试 ToolRegistry — 注册、查找、枚举、清除。"""

import pytest

from tools.base import BaseTool


# ── register ─────────────────────────────────────────────────────────

class TestRegister:
    """工具注册相关测试。"""

    def test_register_valid_tool(self, empty_registry, simple_tool):
        """注册有效工具后可通过 get 获取。"""
        empty_registry.register(simple_tool)
        assert empty_registry.get("simple_tool") is simple_tool

    def test_register_multiple_tools(self, empty_registry, simple_tool, failing_tool):
        """注册多个工具，list_tools 返回全部。"""
        empty_registry.register(simple_tool)
        empty_registry.register(failing_tool)
        assert len(empty_registry.list_tools()) == 2

    def test_register_non_basetool_raises_typeerror(self, empty_registry):
        """注册非 BaseTool 对象抛出 TypeError。"""
        with pytest.raises(TypeError, match="Expected a BaseTool instance"):
            empty_registry.register("not a tool")  # type: ignore[arg-type]

    def test_register_none_raises_typeerror(self, empty_registry):
        """注册 None 抛出 TypeError。"""
        with pytest.raises(TypeError, match="Expected a BaseTool instance"):
            empty_registry.register(None)  # type: ignore[arg-type]

    def test_register_empty_name_raises_valueerror(self, empty_registry):
        """注册 name 为空的工具抛出 ValueError。"""
        from tests.conftest import EmptyNameTool
        with pytest.raises(ValueError, match="non-empty name"):
            empty_registry.register(EmptyNameTool())

    def test_register_duplicate_name_overwrites(self, empty_registry, simple_tool):
        """同名注册覆盖旧工具。"""
        from tests.conftest import SimpleTool
        tool1 = SimpleTool()
        tool2 = SimpleTool()
        empty_registry.register(tool1)
        empty_registry.register(tool2)
        assert empty_registry.get("simple_tool") is tool2
        assert empty_registry.get("simple_tool") is not tool1

    def test_register_preserves_tool_identity(self, empty_registry, simple_tool):
        """注册后 get 返回同一对象。"""
        empty_registry.register(simple_tool)
        assert empty_registry.get("simple_tool") is simple_tool


# ── unregister ───────────────────────────────────────────────────────

class TestUnregister:
    """工具注销相关测试。"""

    def test_unregister_existing_tool(self, populated_registry):
        """注销已注册工具后 get 返回 None。"""
        populated_registry.unregister("simple_tool")
        assert populated_registry.get("simple_tool") is None

    def test_unregister_nonexistent_no_error(self, empty_registry):
        """注销不存在的工具不抛异常。"""
        empty_registry.unregister("nonexistent")

    def test_unregister_then_list_empty(self, populated_registry):
        """注册一个→注销→list 为空。"""
        populated_registry.unregister("simple_tool")
        populated_registry.unregister("failing_tool")
        assert populated_registry.list_tools() == []


# ── get ──────────────────────────────────────────────────────────────

class TestGet:
    """工具查找相关测试。"""

    def test_get_existing_tool(self, populated_registry):
        """获取存在的工具返回正确实例。"""
        tool = populated_registry.get("simple_tool")
        assert isinstance(tool, BaseTool)
        assert tool.name == "simple_tool"

    def test_get_nonexistent_returns_none(self, empty_registry):
        """获取不存在的工具返回 None。"""
        assert empty_registry.get("nonexistent") is None

    def test_get_after_unregister_returns_none(self, populated_registry):
        """注销后 get 返回 None。"""
        populated_registry.unregister("simple_tool")
        assert populated_registry.get("simple_tool") is None

    def test_get_empty_registry_returns_none(self, empty_registry):
        """空注册表 get 返回 None。"""
        assert empty_registry.get("anything") is None


# ── list_tools ───────────────────────────────────────────────────────

class TestListTools:
    """工具列表相关测试。"""

    def test_list_tools_empty(self, empty_registry):
        """空注册表返回空列表。"""
        assert empty_registry.list_tools() == []

    def test_list_tools_populated(self, populated_registry):
        """注册两个工具后返回两个条目。"""
        tools = populated_registry.list_tools()
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"simple_tool", "failing_tool"}

    def test_list_tools_structure(self, populated_registry):
        """每个条目包含 name 和 description。"""
        for tool_info in populated_registry.list_tools():
            assert "name" in tool_info
            assert "description" in tool_info
            assert isinstance(tool_info["name"], str)
            assert isinstance(tool_info["description"], str)

    def test_list_tools_after_clear_returns_empty(self, populated_registry):
        """clear 后 list 为空。"""
        populated_registry.clear()
        assert populated_registry.list_tools() == []


# ── get_all_schemas ──────────────────────────────────────────────────

class TestGetAllSchemas:
    """Schema 收集相关测试。"""

    def test_get_all_schemas_empty(self, empty_registry):
        """空注册表返回空列表。"""
        assert empty_registry.get_all_schemas() == []

    def test_get_all_schemas_populated(self, populated_registry):
        """已注册工具的 schema 被收集到列表中。"""
        schemas = populated_registry.get_all_schemas()
        assert len(schemas) == 2
        for schema in schemas:
            assert isinstance(schema, dict)

    def test_get_all_schemas_count_matches_list(self, populated_registry):
        """schema 数量与工具数量一致。"""
        assert len(populated_registry.get_all_schemas()) == len(
            populated_registry.list_tools()
        )


# ── clear ────────────────────────────────────────────────────────────

class TestClear:
    """清空注册表相关测试。"""

    def test_clear_empties_registry(self, populated_registry):
        """clear 后所有工具不可访问。"""
        populated_registry.clear()
        assert populated_registry.list_tools() == []
        assert populated_registry.get("simple_tool") is None
        assert populated_registry.get("failing_tool") is None

    def test_clear_on_empty_registry_no_error(self, empty_registry):
        """空注册表 clear 不抛异常。"""
        empty_registry.clear()

    def test_clear_is_idempotent(self, populated_registry):
        """连续 clear 两次不抛异常。"""
        populated_registry.clear()
        populated_registry.clear()
        assert populated_registry.list_tools() == []
