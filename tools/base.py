"""基础抽象类 — 所有工具的基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """工具执行的统一返回结果。"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """所有工具必须继承的抽象基类。"""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具的核心逻辑。"""
        ...

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """返回工具的 JSON Schema 定义。"""
        ...

    def validate_params(self, params: Dict[str, Any]) -> None:
        """验证输入参数。"""
        ...
