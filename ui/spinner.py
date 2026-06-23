"""
终端旋转计时器 — 在长时间操作期间显示实时进度。

使用独立线程驱动旋转字符 + 实时计时，写入 stderr 以避免
与 stdout 上的流式输出冲突。

用法:
    with Spinner("正在调用模型..."):
        result = slow_operation()

    with Spinner("执行中..."):
        await async_operation()
"""

import itertools
import sys
import threading
import time
from typing import Optional


class Spinner:
    """终端旋转计时器，在上下文管理器期间显示实时旋转字符和已用时间。

    特性:
    - 每 0.1s 刷新，计时到 0.1s 精度
    - 输出到 stderr，不与 stdout 流式内容冲突
    - Unicode 旋转字符在编码异常时自动回退到 ASCII
    - 作为上下文管理器使用，确保异常时也能正确停止
    """

    _SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _FALLBACK_CHARS = ["|", "/", "-", "\\"]

    def __init__(self, message: str = "处理中"):
        """
        Args:
            message: 旋转计时器旁显示的状态文本
        """
        self._message = message
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0

        # 检测 stderr 是否支持 Unicode
        try:
            "\u2800".encode(sys.stderr.encoding or "utf-8")
            self._chars = self._SPINNER_CHARS
        except (UnicodeEncodeError, LookupError):
            self._chars = self._FALLBACK_CHARS

    # ── 公共接口 ──────────────────────────────────────────────

    def start(self) -> None:
        """启动旋转计时器线程。"""
        if self._running:
            return
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_message: Optional[str] = None, silent: bool = False) -> None:
        """停止旋转计时器，清除行并可选打印完成摘要。

        Args:
            final_message: 可选的最终消息。None 时使用默认格式。
            silent: True 时只清除行不打印任何消息（由调用方自行输出状态）。
        """
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=0.5)
        elapsed = time.time() - self._start_time

        # 清除当前行
        sys.stderr.write("\r\033[K")
        if not silent:
            if final_message is not None:
                sys.stderr.write(f"{final_message}  ({elapsed:.1f}s)\n")
            else:
                sys.stderr.write(f"   ✅ {self._message} — 完成 ({elapsed:.1f}s)\n")
        sys.stderr.flush()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    # ── 内部 ──────────────────────────────────────────────────

    def _spin(self) -> None:
        """旋转线程主循环：每 0.1s 刷新一行到 stderr。"""
        spinner_cycle = itertools.cycle(self._chars)
        while self._running:
            elapsed = time.time() - self._start_time
            char = next(spinner_cycle)
            sys.stderr.write(f"\r  {char} {self._message} ({elapsed:.1f}s)")
            sys.stderr.flush()
            time.sleep(0.1)
