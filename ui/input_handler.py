"""
美化的终端输入处理器 — 基于 prompt_toolkit 构建。

提供带有样式的输入框，上下各有装饰线，以 > 开头。
支持 / 命令补全和 @ 文件选择。

当 prompt_toolkit 不可用（非 Windows 控制台 / CI 环境）时，
自动回退到内置 input() 以保证兼容性。
"""

import os
import shutil
import sys
from typing import Optional

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.history import InMemoryHistory

from ui.completer import ChatCompleter


# ── 终端宽度 ──────────────────────────────────────────────────

def _terminal_width() -> int:
    """获取终端宽度，默认 80。"""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


# ── 输入框样式 ────────────────────────────────────────────────

INPUT_STYLE = Style.from_dict({
    # 输入文本
    "": "fg:ansiwhite",
    # 提示符 >
    "prompt": "fg:ansigreen bold",
    # 补全菜单
    "completion-menu": "bg:ansiblack fg:ansiwhite",
    "completion-menu.completion": "bg:ansiblack fg:ansibrightblack",
    "completion-menu.completion.current": "bg:ansicyan fg:ansiwhite bold",
    # 底部工具栏（装饰线）
    "bottom-toolbar": "fg:ansibrightblack",
    # 光标
    "cursor": "fg:ansigreen",
})


# ── 底部工具栏（显示下装饰线）────────────────────────────────

def _bottom_toolbar_fn() -> FormattedText:
    """生成底部工具栏：下装饰线 + 快捷键提示。"""
    w = min(_terminal_width(), 100)
    line = "─" * w
    hints = " Tab:补全  Ctrl+D:退出"
    # 将提示叠在右侧
    if w > 60:
        combined = line[: w - len(hints)] + hints
    else:
        combined = line
    return FormattedText([("class:bottom-toolbar", combined)])


# ── 顶部装饰线（输入框上方）──────────────────────────────────

def _print_top_deco() -> None:
    """打印顶部装饰线。"""
    w = min(_terminal_width(), 100)
    line = "─" * w
    print(f"\n{line}")


# ── 装饰线下半部分（fallback 模式用）─────────────────────────

def _print_bottom_deco() -> None:
    """打印底部装饰线。"""
    w = min(_terminal_width(), 100)
    line = "─" * w
    print(line)


# ── Windows 控制台检测 ────────────────────────────────────────

def _has_real_windows_console() -> bool:
    """
    检测当前是否运行在真正的 Windows 控制台中。

    VS Code / JetBrains IDE 内置终端使用 ConPTY（伪控制台），
    GetConsoleWindow() 会返回 NULL。prompt_toolkit 在这些环境下可能卡死。
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd == 0:
            # ConPTY / 伪控制台 — 不支持 prompt_toolkit 的 Win32 模式
            return False
        return True
    except Exception:
        return False


def _is_prompt_toolkit_available() -> bool:
    """检测当前环境是否支持 prompt_toolkit 的完整功能。"""
    # 非 TTY 环境（管道、CI）不可用
    if not sys.stdin.isatty():
        return False
    if sys.platform == "win32":
        # 只有真正的 Windows 控制台才支持 prompt_toolkit
        if not _has_real_windows_console():
            return False
    return True


# ── 输入处理器 ────────────────────────────────────────────────

class InputSession:
    """
    终端输入会话 — 封装 prompt_toolkit 输入循环。

    当 prompt_toolkit 不可用时自动回退到内置 input()，
    保证在不同终端环境下都能正常工作。

    用法:
        session = InputSession()
        text = session.prompt()
        if text is None:
            # 用户退出
            return
        # 处理 text

    在 asyncio 上下文中:
        text = await asyncio.to_thread(session.prompt)
    """

    def __init__(
        self,
        completer: Optional[Completer] = None,
        history: Optional[InMemoryHistory] = None,
    ):
        self._completer = completer or ChatCompleter()
        self._history = history or InMemoryHistory()
        self._key_bindings = self._create_key_bindings()
        self._first_prompt = True
        self._use_enhanced = _is_prompt_toolkit_available()

    # ── 键位绑定 ────────────────────────────────────────────

    def _create_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("c-d")
        def _(event):
            """Ctrl+D 退出。"""
            event.app.exit(result=None)

        @kb.add("escape", "enter")
        def _(event):
            """Alt+Enter 插入换行。"""
            event.current_buffer.insert_text("\n")

        return kb

    # ── 提示符 ──────────────────────────────────────────────

    def _get_prompt(self) -> FormattedText:
        """构建带样式的提示符文本。"""
        return FormattedText([
            ("class:prompt", "> "),
        ])

    # ── 增强模式输入（prompt_toolkit）────────────────────────

    def _prompt_enhanced(self) -> Optional[str]:
        """使用 prompt_toolkit 进行美化的输入。"""
        try:
            text = pt_prompt(
                message=self._get_prompt,
                style=INPUT_STYLE,
                completer=self._completer,
                history=self._history,
                key_bindings=self._key_bindings,
                bottom_toolbar=_bottom_toolbar_fn,
                multiline=False,
                cursor=CursorShape.BEAM,
                enable_system_prompt=True,
                complete_while_typing=True,
                mouse_support=False,
            )
            return text
        except (EOFError, KeyboardInterrupt):
            return None
        except Exception as e:
            # prompt_toolkit 运行时异常 → 永久切换到回退模式
            print(f"\n⚠️ 增强输入不可用 ({e})，已切换到基本模式。")
            self._use_enhanced = False
            return None  # 这轮返回空，让调用方重试

    # ── 回退模式输入（内置 input）────────────────────────────

    def _prompt_fallback(self) -> Optional[str]:
        """使用内置 input() 进行简化输入（无补全功能）。"""
        try:
            # 显示底部装饰线
            _print_bottom_deco()
            # 使用 > 作为提示符
            text = input("> ")
            return text
        except (EOFError, KeyboardInterrupt):
            return None

    # ── 输入方法 ────────────────────────────────────────────

    def prompt(self) -> Optional[str]:
        """
        显示输入框并等待用户输入（同步方法，在 asyncio 中需用 to_thread 包装）。

        自动选择增强模式（prompt_toolkit）或回退模式（内置 input）。
        增强模式失败时自动降级为回退模式。

        Returns:
            用户输入的文本，如果用户按 Ctrl+D 则返回 None。
        """
        # 首次调用打印顶部装饰线
        if self._first_prompt:
            _print_top_deco()
            self._first_prompt = False

        if self._use_enhanced:
            result = self._prompt_enhanced()
            # 如果增强模式失败（降级），重试回退模式
            if not self._use_enhanced:
                return self._prompt_fallback()
            return result
        else:
            return self._prompt_fallback()

    # ── 重置顶部装饰线 ──────────────────────────────────────

    def reset_deco(self) -> None:
        """下一轮输入前重置顶部装饰线标记。"""
        self._first_prompt = True


# ── 工厂函数 ──────────────────────────────────────────────────

def create_input_handler() -> InputSession:
    """创建并返回一个 InputSession 实例。"""
    return InputSession()
