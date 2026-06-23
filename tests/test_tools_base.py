"""测试 ToolResult dataclass 与 BaseTool 抽象基类。"""

import pytest

from tools.base import BaseTool, ToolResult


# ── ToolResult ───────────────────────────────────────────────────────

class TestToolResult:
    """ToolResult dataclass 相关测试。"""

    def test_success_defaults(self):
        """成功结果：data/error/metadata 均使用默认值。"""
        result = ToolResult(success=True)
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.metadata == {}

    def test_failure_with_error(self):
        """失败结果：设置对应的 error 消息。"""
        result = ToolResult(success=False, error="something broke")
        assert result.success is False
        assert result.error == "something broke"
        assert result.data is None

    def test_with_data(self):
        """携带数据的结果。"""
        result = ToolResult(success=True, data={"key": "value"})
        assert result.data == {"key": "value"}

    def test_metadata_defaults_to_empty_dict(self):
        """未指定 metadata 时，默认为空 dict。"""
        result = ToolResult(success=True)
        assert isinstance(result.metadata, dict)
        assert result.metadata == {}

    def test_metadata_custom(self):
        """自定义 metadata。"""
        result = ToolResult(success=True, metadata={"duration_ms": 42})
        assert result.metadata == {"duration_ms": 42}

    def test_is_dataclass(self):
        """ToolResult 是 dataclass。"""
        assert hasattr(ToolResult, "__dataclass_fields__")

    def test_mutable_metadata_isolation(self):
        """两个 ToolResult 实例的 metadata 互不影响。"""
        r1 = ToolResult(success=True)
        r2 = ToolResult(success=True)
        r1.metadata["key"] = "value"
        assert r2.metadata == {}
        assert r1.metadata["key"] == "value"


# ── BaseTool ─────────────────────────────────────────────────────────

class TestBaseTool:
    """BaseTool 抽象基类相关测试。"""

    def test_cannot_instantiate_abstract_base(self):
        """直接实例化 BaseTool 应抛出 TypeError。"""
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore[abstract]

    def test_can_instantiate_concrete_subclass(self):
        """可以实例化实现了全部抽象方法的具体子类。"""
        from tests.conftest import SimpleTool
        tool = SimpleTool()
        assert isinstance(tool, BaseTool)

    def test_concrete_subclass_has_name(self):
        from tests.conftest import SimpleTool
        assert SimpleTool().name == "simple_tool"

    def test_concrete_subclass_has_description(self):
        from tests.conftest import SimpleTool
        assert SimpleTool().description == "A simple test tool"

    @pytest.mark.asyncio
    async def test_concrete_execute_returns_toolresult(self):
        """execute 返回 ToolResult 实例。"""
        from tests.conftest import SimpleTool
        result = await SimpleTool().execute()
        assert isinstance(result, ToolResult)

    @pytest.mark.asyncio
    async def test_concrete_execute_success_value(self):
        """execute 传递参数并返回正确的 data。"""
        from tests.conftest import SimpleTool
        result = await SimpleTool().execute(input="hello")
        assert result.success is True
        assert result.data == "hello"

    def test_concrete_get_schema_returns_dict(self):
        from tests.conftest import SimpleTool
        schema = SimpleTool().get_schema()
        assert isinstance(schema, dict)

    def test_validate_params_default_noop(self):
        """validate_params 默认不执行任何操作（空方法体）。"""
        from tests.conftest import SimpleTool
        tool = SimpleTool()
        # 不应抛异常
        tool.validate_params({"anything": 123})

    def test_missing_execute_abstract_error(self):
        """未实现 execute 时不能实例化。"""
        from tests.conftest import IncompleteTool
        with pytest.raises(TypeError):
            IncompleteTool()  # type: ignore[abstract]

    def test_missing_get_schema_abstract_error(self):
        """未实现 get_schema 时不能实例化。"""
        from tests.conftest import MissingSchemaTool
        with pytest.raises(TypeError):
            MissingSchemaTool()  # type: ignore[abstract]
