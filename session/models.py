"""会话数据模型 — Pydantic 定义的消息和会话结构。"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    """单条对话消息，兼容 OpenAI chat completion 格式。"""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    reasoning_content: Optional[str] = None


class Session(BaseModel):
    """一次对话会话，包含完整的消息历史与元数据。"""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str = "Unnamed Session"
    agent_name: str = "default"
    messages: List[Message] = Field(default_factory=list)
    turn_count: int = 0
    max_turns: int = 50
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_message(self, msg: Message) -> None:
        """添加一条消息并更新修改时间。"""
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()

    def to_api_messages(self) -> List[Dict[str, Any]]:
        """
        将内部消息转换为 LLM API 可接受的格式。

        系统消息由 Agent 动态生成，此处跳过以避免重复。
        """
        api_messages: List[Dict[str, Any]] = []
        for msg in self.messages:
            if msg.role == "system":
                continue
            entry: Dict[str, Any] = {"role": msg.role}

            if msg.content is not None:
                entry["content"] = msg.content

            if msg.tool_calls is not None:
                entry["tool_calls"] = msg.tool_calls

            if msg.tool_call_id is not None:
                entry["tool_call_id"] = msg.tool_call_id

            if msg.name is not None:
                entry["name"] = msg.name

            if msg.reasoning_content:
                entry["reasoning_content"] = msg.reasoning_content

            api_messages.append(entry)

        return api_messages

    def get_system_prompt(self) -> Optional[str]:
        """获取会话的系统提示词（如果存在）。"""
        for msg in self.messages:
            if msg.role == "system":
                return msg.content
        return None
