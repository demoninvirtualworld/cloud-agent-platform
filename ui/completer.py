"""
自定义补全器 — 支持 / 命令补全和 @ 文件路径补全。

- / → 补全内置命令（/exit, /help, /clear, /save, /version）
- @ → 补全文件系统路径（相对当前工作目录）
"""

import os
from typing import Iterable, Optional

from prompt_toolkit.completion import (
    Completer,
    Completion,
    PathCompleter,
    merge_completers,
)
from prompt_toolkit.document import Document


# ── 内置命令列表 ──────────────────────────────────────────────

BUILTIN_COMMANDS: list[dict] = [
    {"command": "/exit", "description": "退出对话"},
    {"command": "/quit", "description": "退出对话"},
    {"command": "/help", "description": "显示帮助信息"},
    {"command": "/clear", "description": "清屏"},
    {"command": "/save", "description": "保存当前会话"},
    {"command": "/version", "description": "显示版本信息"},
    {"command": "/model", "description": "切换模型"},
    {"command": "/list", "description": "列出已保存的会话"},
    {"command": "/resume", "description": "恢复指定会话"},
    {"command": "/delete", "description": "删除指定会话"},
]


# ── 命令补全器 ────────────────────────────────────────────────

class SlashCommandCompleter(Completer):
    """根据内置命令列表提供 / 命令补全。"""

    def __init__(self, commands: Optional[list[dict]] = None):
        self._commands = commands or BUILTIN_COMMANDS

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        text = document.text_before_cursor

        # 只在以 / 开头时补全
        if not text.startswith("/"):
            return

        # 找到最后一个 / 开头的词
        last_slash_idx = text.rfind("/")
        if last_slash_idx == -1:
            return

        word = text[last_slash_idx:]

        for cmd in self._commands:
            if cmd["command"].startswith(word):
                yield Completion(
                    cmd["command"],
                    start_position=-len(word),
                    display=cmd["command"],
                    display_meta=cmd.get("description", ""),
                    style="fg:ansicyan bold",
                    selected_style="fg:ansicyan bg:ansiwhite bold",
                )


# ── @ 文件路径补全器 ──────────────────────────────────────────

class AtFileCompleter(Completer):
    """@ 后补全文件系统路径，相对当前工作目录。"""

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        text = document.text_before_cursor

        # 找到最后一个 @ 的位置
        last_at_idx = text.rfind("@")
        if last_at_idx == -1:
            return

        # @ 之后的文本作为路径前缀
        path_prefix = text[last_at_idx + 1:]

        # 确定搜索目录和前缀
        search_dir = os.getcwd()
        if path_prefix:
            # 用户输入了部分路径
            full_prefix = os.path.join(search_dir, path_prefix)
            if os.path.isdir(path_prefix):
                search_dir = path_prefix
                file_prefix = ""
            else:
                search_dir = os.path.dirname(full_prefix) if os.path.dirname(full_prefix) else search_dir
                file_prefix = os.path.basename(path_prefix)
        else:
            file_prefix = ""

        # 安全：确保搜索目录存在
        if not os.path.isdir(search_dir):
            return

        try:
            entries = sorted(os.listdir(search_dir))
        except PermissionError:
            return

        displayed = 0
        max_entries = 50

        for entry in entries:
            if displayed >= max_entries:
                break
            if file_prefix and not entry.startswith(file_prefix):
                continue

            full_path = os.path.join(search_dir, entry)
            is_dir = os.path.isdir(full_path)

            # 拼接补全后的相对路径
            if path_prefix:
                rel_dir = os.path.dirname(path_prefix)
                if rel_dir:
                    completed = os.path.join(rel_dir, entry)
                else:
                    completed = entry
            else:
                completed = entry

            if is_dir:
                completed += os.sep

            display_text = entry + ("/" if is_dir else "")
            display_meta = "目录" if is_dir else f"文件 ({_format_size(full_path)})"
            style = "fg:ansimagenta bold" if is_dir else "fg:ansimagenta"

            yield Completion(
                completed,
                start_position=-(len(path_prefix) + 1),  # +1 for @
                display=display_text,
                display_meta=display_meta,
                style=style,
                selected_style="fg:ansimagenta bg:ansiwhite bold",
            )
            displayed += 1


# ── 合并补全器 ────────────────────────────────────────────────

class ChatCompleter(Completer):
    """合并补全器：根据上下文自动选择 / 命令 或 @ 文件补全。"""

    def __init__(self):
        self._slash = SlashCommandCompleter()
        self._at_file = AtFileCompleter()

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        text = document.text_before_cursor

        # 检查当前光标所在的词是否以 / 开头
        if text.startswith("/"):
            yield from self._slash.get_completions(document, complete_event)
            return

        # 检查是否有 @ 在光标附近
        # 取光标前最后一个词
        last_at = text.rfind("@")
        if last_at != -1:
            # 确保 @ 之后没有空格分词（@ 和路径是连续的）
            after_at = text[last_at:]
            if " " not in after_at:
                yield from self._at_file.get_completions(document, complete_event)
                return


# ── 辅助 ──────────────────────────────────────────────────────

def _format_size(path: str) -> str:
    """将文件大小格式化为人类可读的字符串。"""
    try:
        size = os.path.getsize(path)
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"
    except OSError:
        return "?"
