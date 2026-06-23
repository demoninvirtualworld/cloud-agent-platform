"""会话管理器 — 持久化会话的 CRUD 操作。"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from .models import Session

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSION_DIR = _PROJECT_ROOT / "memory" / "sessions"


class SessionManager:
    """管理会话的持久化存储。每个会话保存为 memory/sessions/<id>.json。"""

    def __init__(self, base_dir: Path = DEFAULT_SESSION_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """获取指定会话的存储文件路径。"""
        safe_id = "".join(c for c in session_id if c.isalnum() or c == "-")
        return self.base_dir / f"{safe_id}.json"

    def create(
        self,
        name: str = "Unnamed Session",
        agent_name: str = "default",
        max_turns: int = 50,
    ) -> Session:
        """创建一个新会话并立即持久化。"""
        session = Session(
            name=name, agent_name=agent_name, max_turns=max_turns
        )
        self.save(session)
        return session

    def save(self, session: Session) -> None:
        """将会话序列化保存到磁盘。"""
        session.updated_at = datetime.now().isoformat()
        path = self._session_path(session.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                session.model_dump(), f, indent=2, ensure_ascii=False
            )

    def load(self, session_id: str) -> Optional[Session]:
        """从磁盘加载指定会话。如果不存在则返回 None。"""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Session(**data)
        except (json.JSONDecodeError, TypeError, ValidationError) as e:
            print(f"⚠️ 加载会话 {session_id} 失败: {e}")
            return None

    def list_sessions(self) -> List[dict]:
        """列出所有已保存的会话摘要信息（按更新时间倒序）。"""
        sessions: List[dict] = []
        json_files = sorted(
            self.base_dir.glob("*.json"),
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )
        for f in json_files:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                sessions.append(
                    {
                        "id": data.get("id", ""),
                        "name": data.get("name", "Unnamed"),
                        "agent_name": data.get("agent_name", "default"),
                        "turn_count": data.get("turn_count", 0),
                        "max_turns": data.get("max_turns", 50),
                        "message_count": len(data.get("messages", [])),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def delete(self, session_id: str) -> bool:
        """删除指定会话的存储文件。返回是否成功删除。"""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        """检查指定会话是否存在。"""
        return self._session_path(session_id).exists()
