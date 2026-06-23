"""测试 Message 与 Session Pydantic 数据模型。"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from session.models import Message, Session


# ── Message ──────────────────────────────────────────────────────────

class TestMessage:
    """Message 模型相关测试。"""

    def test_message_creation_minimal(self):
        """最小创建：仅 role 必填。"""
        msg = Message(role="user")
        assert msg.role == "user"
        assert msg.content is None
        assert msg.tool_calls is None
        assert msg.tool_call_id is None
        assert msg.name is None
        assert msg.reasoning_content is None

    def test_message_creation_with_content(self):
        """带 content 的消息。"""
        msg = Message(role="user", content="Hello, world!")
        assert msg.content == "Hello, world!"

    def test_message_creation_with_tool_calls(self):
        """带 tool_calls 的 assistant 消息。"""
        tool_calls = [{"id": "call_1", "function": {"name": "test", "arguments": "{}"}}]
        msg = Message(role="assistant", tool_calls=tool_calls)
        assert msg.tool_calls == tool_calls

    def test_message_creation_with_tool_call_id(self):
        """带 tool_call_id 的 tool 消息。"""
        msg = Message(role="tool", tool_call_id="call_123")
        assert msg.tool_call_id == "call_123"

    def test_message_creation_with_name(self):
        """带 name 的消息。"""
        msg = Message(role="assistant", name="my_function")
        assert msg.name == "my_function"

    def test_message_creation_with_reasoning_content(self):
        """带推理内容的消息（DeepSeek 等模型支持）。"""
        msg = Message(role="assistant", reasoning_content="Let me think...")
        assert msg.reasoning_content == "Let me think..."

    def test_message_role_is_required(self):
        """缺少 role 时抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            Message()

    def test_message_json_roundtrip(self):
        """model_dump → 重建 保持数据一致。"""
        original = Message(
            role="assistant",
            content="Response",
            tool_calls=[{"id": "1", "function": {"name": "f", "arguments": "{}"}}],
            reasoning_content="Thinking...",
        )
        data = original.model_dump()
        restored = Message(**data)
        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.tool_calls == original.tool_calls
        assert restored.reasoning_content == original.reasoning_content


# ── Session ──────────────────────────────────────────────────────────

class TestSession:
    """Session 模型创建与默认值测试。"""

    def test_session_creation_defaults(self):
        """默认创建：id 为 12 字符 hex，其他为默认值。"""
        session = Session()
        assert len(session.id) == 12
        assert session.name == "Unnamed Session"
        assert session.agent_name == "default"
        assert session.messages == []
        assert session.turn_count == 0
        assert session.max_turns == 50

    def test_session_id_is_12_char_hex(self):
        """session.id 为 12 个十六进制字符。"""
        session = Session()
        assert len(session.id) == 12
        assert all(c in "0123456789abcdef" for c in session.id)

    def test_session_ids_are_unique(self):
        """不同 Session 的 id 不同。"""
        ids = {Session().id for _ in range(10)}
        assert len(ids) == 10

    def test_session_created_at_is_isoformat(self):
        """created_at 是合法的 ISO 格式字符串。"""
        session = Session()
        dt = datetime.fromisoformat(session.created_at)
        assert isinstance(dt, datetime)

    def test_session_updated_at_is_isoformat(self):
        """updated_at 是合法的 ISO 格式字符串。"""
        session = Session()
        dt = datetime.fromisoformat(session.updated_at)
        assert isinstance(dt, datetime)

    def test_session_custom_name(self):
        session = Session(name="My Session")
        assert session.name == "My Session"

    def test_session_custom_agent_name(self):
        session = Session(agent_name="gpt-4")
        assert session.agent_name == "gpt-4"

    def test_session_custom_max_turns(self):
        session = Session(max_turns=100)
        assert session.max_turns == 100


# ── Session.add_message ──────────────────────────────────────────────

class TestSessionAddMessage:
    """add_message 方法测试。"""

    def test_add_message_appends(self, sample_session):
        """添加消息后 messages 长度 +1。"""
        before = len(sample_session.messages)
        sample_session.add_message(Message(role="user", content="Hello"))
        assert len(sample_session.messages) == before + 1

    def test_add_message_updates_updated_at(self, sample_session):
        """添加消息后 updated_at 应更新。"""
        import time
        old_updated = sample_session.updated_at
        time.sleep(0.001)  # 确保时间戳不同
        sample_session.add_message(Message(role="user", content="Hi"))
        assert sample_session.updated_at != old_updated

    def test_add_multiple_messages(self, sample_session):
        """添加 3 条消息，顺序保持。"""
        msgs = [
            Message(role="user", content="1"),
            Message(role="assistant", content="2"),
            Message(role="user", content="3"),
        ]
        for m in msgs:
            sample_session.add_message(m)
        assert len(sample_session.messages) == 3
        assert [m.content for m in sample_session.messages] == ["1", "2", "3"]


# ── Session.to_api_messages ──────────────────────────────────────────

class TestToApiMessages:
    """to_api_messages 方法测试。"""

    def test_to_api_messages_empty(self):
        """空会话返回空列表。"""
        session = Session()
        assert session.to_api_messages() == []

    def test_to_api_messages_skips_system(self):
        """system 消息被跳过。"""
        session = Session()
        session.add_message(Message(role="system", content="You are helpful"))
        session.add_message(Message(role="user", content="Hello"))
        api_msgs = session.to_api_messages()
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_to_api_messages_includes_content(self):
        """user 消息的 content 被包含。"""
        session = Session()
        session.add_message(Message(role="user", content="Hello"))
        assert session.to_api_messages()[0]["content"] == "Hello"

    def test_to_api_messages_includes_tool_calls(self):
        """assistant 消息的 tool_calls 被包含。"""
        tool_calls = [{"id": "1", "function": {"name": "f", "arguments": "{}"}}]
        session = Session()
        session.add_message(Message(role="assistant", tool_calls=tool_calls))
        assert session.to_api_messages()[0]["tool_calls"] == tool_calls

    def test_to_api_messages_includes_tool_call_id(self):
        """tool 消息的 tool_call_id 被包含。"""
        session = Session()
        session.add_message(Message(role="tool", tool_call_id="call_abc"))
        assert session.to_api_messages()[0]["tool_call_id"] == "call_abc"

    def test_to_api_messages_includes_name(self):
        """消息的 name 字段被包含。"""
        session = Session()
        session.add_message(Message(role="assistant", name="my_tool"))
        assert session.to_api_messages()[0]["name"] == "my_tool"

    def test_to_api_messages_includes_reasoning_content(self):
        """assistant 消息的 reasoning_content 被包含。"""
        session = Session()
        session.add_message(
            Message(role="assistant", content="Answer", reasoning_content="Hmm...")
        )
        api_msg = session.to_api_messages()[0]
        assert "reasoning_content" in api_msg
        assert api_msg["reasoning_content"] == "Hmm..."

    def test_to_api_messages_excludes_none_reasoning(self):
        """没有 reasoning_content 时不添加该 key。"""
        session = Session()
        session.add_message(Message(role="assistant", content="Answer"))
        api_msg = session.to_api_messages()[0]
        assert "reasoning_content" not in api_msg

    def test_to_api_messages_excludes_none_fields(self):
        """最小消息输出只包含 role（无 None 字段）。"""
        session = Session()
        session.add_message(Message(role="user"))
        api_msg = session.to_api_messages()[0]
        assert api_msg == {"role": "user"}


# ── Session.get_system_prompt ────────────────────────────────────────

class TestGetSystemPrompt:
    """get_system_prompt 方法测试。"""

    def test_get_system_prompt_returns_first_system(self):
        """返回第一条 system 消息的 content。"""
        session = Session()
        session.add_message(Message(role="system", content="You are helpful"))
        session.add_message(Message(role="system", content="You are also helpful"))
        session.add_message(Message(role="user", content="Hello"))
        assert session.get_system_prompt() == "You are helpful"

    def test_get_system_prompt_no_system_returns_none(self):
        """只有 user 消息时返回 None。"""
        session = Session()
        session.add_message(Message(role="user", content="Hello"))
        assert session.get_system_prompt() is None

    def test_get_system_prompt_empty_session_returns_none(self):
        """空会话返回 None。"""
        session = Session()
        assert session.get_system_prompt() is None
