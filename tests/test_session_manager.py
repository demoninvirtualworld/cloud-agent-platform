"""测试 SessionManager — 会话持久化 CRUD 操作。"""

import json
import time
from pathlib import Path

import pytest

from session.manager import SessionManager
from session.models import Message, Session


# ── 帮助函数 ─────────────────────────────────────────────────────────

def _write_file(path: Path, content: str) -> None:
    """写入文件，自动创建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── 构造函数与路径 ──────────────────────────────────────────────────

class TestSessionManagerInit:
    """SessionManager 构造函数测试。"""

    def test_creates_directory(self, tmp_path):
        """构造函数自动创建存储目录。"""
        base = tmp_path / "sessions"
        assert not base.exists()
        SessionManager(base_dir=base)
        assert base.exists()
        assert base.is_dir()

    def test_uses_default_dir(self):
        """默认使用 memory/sessions 路径。"""
        manager = SessionManager()
        # 相对路径在 mkdir 时被解析为绝对路径
        assert manager.base_dir.name == "sessions"
        assert "memory" in str(manager.base_dir)

    def test_session_path_sanitizes_id(self, tmp_path):
        """session_id 被消毒，只保留字母数字和连字符。"""
        manager = SessionManager(base_dir=tmp_path)
        path = manager._session_path("abc/../123")
        # 不应包含 / 或 ..
        assert "/" not in str(path.name)
        assert ".." not in str(path.name)

    def test_session_path_sanitizes_special_chars(self, tmp_path):
        """特殊字符被移除。"""
        manager = SessionManager(base_dir=tmp_path)
        path = manager._session_path("test!@#.json")
        # ! @ # 被移除或替换
        name = path.name
        assert "!" not in name
        assert "@" not in name
        assert "#" not in name
        assert ".json" in name

    def test_session_path_sanitizes_chinese(self, tmp_path):
        """中文字符通过 isalnum() 检查（Unicode 字母），被保留。"""
        manager = SessionManager(base_dir=tmp_path)
        path = manager._session_path("路径名")
        name = path.stem  # 不含 .json 后缀
        # Python 3 中 isalnum() 对 CJK 字符返回 True，因此被保留
        assert "路" in name
        assert "径" in name
        assert "名" in name


# ── create ───────────────────────────────────────────────────────────

class TestCreate:
    """SessionManager.create 测试。"""

    def test_create_session_returns_session(self, tmp_path):
        """create 返回 Session 实例。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        assert isinstance(session, Session)

    def test_create_session_persists_to_disk(self, tmp_path):
        """create 后文件存在且 session_exists 为 True。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        assert manager.session_exists(session.id)
        assert manager._session_path(session.id).exists()

    def test_create_session_with_custom_name(self, tmp_path):
        """自定义会话名称。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create(name="Custom Name")
        assert session.name == "Custom Name"

    def test_create_session_with_custom_agent(self, tmp_path):
        """自定义 agent_name。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create(agent_name="test-agent")
        assert session.agent_name == "test-agent"

    def test_create_session_with_custom_max_turns(self, tmp_path):
        """自定义 max_turns。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create(max_turns=99)
        assert session.max_turns == 99


# ── save ─────────────────────────────────────────────────────────────

class TestSave:
    """SessionManager.save 测试。"""

    def test_save_updates_updated_at(self, tmp_path):
        """save 后 updated_at 被更新。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        old_updated = session.updated_at
        time.sleep(0.001)
        manager.save(session)
        assert session.updated_at != old_updated


# ── load ─────────────────────────────────────────────────────────────

class TestLoad:
    """SessionManager.load 测试。"""

    def test_load_existing_session(self, tmp_path):
        """加载已创建的会话。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create(name="Load Test")
        loaded = manager.load(session.id)
        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.name == "Load Test"

    def test_load_nonexistent_returns_none(self, tmp_path):
        """加载不存在的会话返回 None。"""
        manager = SessionManager(base_dir=tmp_path)
        assert manager.load("nonexistent") is None

    def test_save_load_roundtrip_preserves_data(self, tmp_path):
        """save → load 往返保持数据完整性。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create(name="Roundtrip")
        session.add_message(Message(role="user", content="Hello"))
        session.add_message(Message(role="assistant", content="Hi there!"))
        session.turn_count = 3
        manager.save(session)

        loaded = manager.load(session.id)
        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.name == session.name
        assert loaded.agent_name == session.agent_name
        assert loaded.turn_count == session.turn_count
        assert loaded.max_turns == session.max_turns
        assert len(loaded.messages) == len(session.messages)
        for orig, restored in zip(session.messages, loaded.messages):
            assert orig.role == restored.role
            assert orig.content == restored.content

    def test_load_corrupted_json_returns_none(self, tmp_path):
        """损坏的 JSON 文件返回 None。"""
        manager = SessionManager(base_dir=tmp_path)
        path = manager._session_path("corrupt")
        _write_file(path, "this is not valid json")
        assert manager.load("corrupt") is None

    def test_load_valid_json_invalid_model_returns_none(self, tmp_path):
        """合法 JSON 但字段类型不匹配时返回 None。"""
        manager = SessionManager(base_dir=tmp_path)
        path = manager._session_path("invalid-model")
        # messages 字段类型错误：应为 list 但给了 string
        _write_file(path, '{"id": "abc123", "messages": "not_a_list"}')
        assert manager.load("invalid-model") is None

    def test_load_session_with_messages_preserves_order(self, tmp_path):
        """加载后消息顺序与保存时一致。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        contents = ["first", "second", "third"]
        for c in contents:
            session.add_message(Message(role="user", content=c))
        manager.save(session)

        loaded = manager.load(session.id)
        assert loaded is not None
        loaded_contents = [m.content for m in loaded.messages]
        assert loaded_contents == contents

    def test_load_session_with_reasoning_content(self, tmp_path):
        """加载带 reasoning_content 的会话。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        session.add_message(
            Message(role="assistant", content="Answer", reasoning_content="Hmm...")
        )
        manager.save(session)

        loaded = manager.load(session.id)
        assert loaded is not None
        assert loaded.messages[0].reasoning_content == "Hmm..."


# ── list_sessions ────────────────────────────────────────────────────

class TestListSessions:
    """SessionManager.list_sessions 测试。"""

    def test_list_sessions_empty(self, tmp_path):
        """空目录返回空列表。"""
        manager = SessionManager(base_dir=tmp_path)
        assert manager.list_sessions() == []

    def test_list_sessions_returns_all(self, tmp_path):
        """创建 3 个会话，列出全部。"""
        manager = SessionManager(base_dir=tmp_path)
        for i in range(3):
            manager.create(name=f"Session {i}")
        assert len(manager.list_sessions()) == 3

    def test_list_sessions_structure(self, tmp_path):
        """每个条目包含正确的键。"""
        manager = SessionManager(base_dir=tmp_path)
        manager.create(name="Test")
        entries = manager.list_sessions()
        assert len(entries) == 1
        keys = {"id", "name", "agent_name", "turn_count", "max_turns",
                "message_count", "created_at", "updated_at"}
        assert keys <= set(entries[0].keys())

    def test_list_sessions_sorted_by_updated(self, tmp_path):
        """按更新时间倒序排列。"""
        manager = SessionManager(base_dir=tmp_path)
        s1 = manager.create(name="First")
        time.sleep(0.01)
        s2 = manager.create(name="Second")
        time.sleep(0.01)
        s3 = manager.create(name="Third")

        entries = manager.list_sessions()
        # 最后创建的应该在最前面
        assert entries[0]["id"] == s3.id
        assert entries[2]["id"] == s1.id

    def test_list_sessions_skips_corrupted_files(self, tmp_path):
        """损坏的 JSON 文件被跳过。"""
        manager = SessionManager(base_dir=tmp_path)
        manager.create(name="Valid")
        _write_file(manager._session_path("corrupt"), "garbage")
        entries = manager.list_sessions()
        assert len(entries) == 1
        assert entries[0]["name"] == "Valid"


# ── delete ───────────────────────────────────────────────────────────

class TestDelete:
    """SessionManager.delete 测试。"""

    def test_delete_existing_session(self, tmp_path):
        """删除存在的会话返回 True，文件消失。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        assert manager.delete(session.id) is True
        assert not manager.session_exists(session.id)

    def test_delete_nonexistent_returns_false(self, tmp_path):
        """删除不存在的会话返回 False。"""
        manager = SessionManager(base_dir=tmp_path)
        assert manager.delete("nonexistent") is False

    def test_delete_idempotent(self, tmp_path):
        """连续删除：第一次 True，第二次 False。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        assert manager.delete(session.id) is True
        assert manager.delete(session.id) is False


# ── session_exists ───────────────────────────────────────────────────

class TestSessionExists:
    """SessionManager.session_exists 测试。"""

    def test_session_exists_true(self, tmp_path):
        """创建后 session_exists 为 True。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        assert manager.session_exists(session.id) is True

    def test_session_exists_false(self, tmp_path):
        """随机 ID 返回 False。"""
        manager = SessionManager(base_dir=tmp_path)
        assert manager.session_exists("abcdef123456") is False

    def test_session_exists_after_delete(self, tmp_path):
        """删除后 session_exists 为 False。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        manager.delete(session.id)
        assert manager.session_exists(session.id) is False


# ── 边界与集成 ───────────────────────────────────────────────────────

class TestEdgeCases:
    """边界情况与集成测试。"""

    def test_create_multiple_sessions_unique_ids(self, tmp_path):
        """创建多个会话的 id 全部不同。"""
        manager = SessionManager(base_dir=tmp_path)
        ids = {manager.create().id for _ in range(5)}
        assert len(ids) == 5

    def test_sanitized_path_prevents_directory_traversal(self, tmp_path):
        """消毒后的路径不会逃逸 base_dir。"""
        manager = SessionManager(base_dir=tmp_path)
        path = manager._session_path("../../etc/passwd")
        # 路径应该在 base_dir 之下
        assert str(tmp_path) in str(path.resolve())

    def test_save_updates_updated_at_via_save(self, tmp_path):
        """save 方法更新 updated_at。"""
        manager = SessionManager(base_dir=tmp_path)
        session = manager.create()
        old_updated = session.updated_at
        time.sleep(0.001)
        manager.save(session)
        assert session.updated_at != old_updated
