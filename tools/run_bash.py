"""执行 Shell 命令工具 — 跨平台支持 bash / cmd / PowerShell。"""

import asyncio
import os
import platform
import shutil
import time
from typing import Any, Dict, Optional

from .base import BaseTool, ToolResult


# ── Shell 检测 ──────────────────────────────────────────────────

def _is_wsl_stub(bash_path: str) -> bool:
    """检测是否为 WSL 存根（C:\\Windows\\System32\\bash.exe）。

    Windows 10/11 自带该存根，它会在 WSL 未安装时打印错误并退出。
    它不是真正的 bash，不能用于执行命令。"""
    try:
        normalized = os.path.normpath(bash_path).lower()
        # Windows 系统目录下的 bash.exe 是 WSL 存根
        windir = os.environ.get("WINDIR", r"C:\Windows").lower()
        if normalized.startswith(windir):
            return True
    except Exception:
        pass
    return False


def _verify_bash(bash_path: str) -> bool:
    """验证 bash 是否真的能工作（排除 WSL 存根等不可用的 bash）。"""
    if _is_wsl_stub(bash_path):
        return False
    try:
        import subprocess
        result = subprocess.run(
            [bash_path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and "bash" in result.stdout.lower()
    except Exception:
        return False


def _find_bash() -> Optional[str]:
    """在 Windows 上查找可用的 bash，找不到则返回 None。

    排除 WSL 存根（C:\\Windows\\System32\\bash.exe），
    只返回真正可用的 Git Bash 或 MSYS2 bash。"""
    if platform.system() != "Windows":
        return None
    # 按优先级查找
    candidates = [
        r"E:\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
    ]
    # 也尝试从 PATH 中找
    git_bash = shutil.which("bash")
    if git_bash and not _is_wsl_stub(git_bash):
        candidates.insert(0, git_bash)
    for path in candidates:
        if os.path.isfile(path) and _verify_bash(path):
            return path
    return None


# 延迟初始化：不在模块加载时检测，等第一次实际调用时再检测
# 这样用户可以安装 Git Bash 后直接使用，无需重启进程
_BASH_PATH: Optional[str] = None
_BASH_DETECTED: bool = False
_SHELL_DESC: str = ""


def _ensure_bash_detected() -> None:
    """延迟检测 bash（首次调用时执行，而非模块导入时）。"""
    global _BASH_PATH, _BASH_DETECTED
    if not _BASH_DETECTED:
        _BASH_PATH = _find_bash()
        _BASH_DETECTED = True


def _get_shell_description() -> str:
    """生成当前 Shell 环境的描述文本，供 LLM 生成正确的命令。"""
    global _SHELL_DESC
    if _SHELL_DESC:
        return _SHELL_DESC

    _ensure_bash_detected()
    if _BASH_PATH:
        _SHELL_DESC = (
            "在终端中执行 Shell 命令（bash 环境）。"
            "支持标准 Unix 命令：ls, find, grep, cat, head, tail 等。"
            "也支持 git, python, pip 等开发工具。"
        )
    elif platform.system() == "Windows":
        _SHELL_DESC = (
            "在终端中执行命令（Windows CMD 环境）。"
            "请使用 Windows 命令：dir（而非 ls），findstr（而非 grep），type（而非 cat）等。"
        )
    else:
        _SHELL_DESC = (
            "在终端中执行 Shell 命令（Unix 环境）。"
        )
    return _SHELL_DESC


class RunBashTool(BaseTool):
    name = "run_bash"
    description = _get_shell_description()

    # 默认超时时间（毫秒）
    DEFAULT_TIMEOUT = 120_000
    # 最大超时时间（毫秒）
    MAX_TIMEOUT = 600_000

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        timeout_ms = kwargs.get("timeout", self.DEFAULT_TIMEOUT)
        workdir = kwargs.get("workdir", None)

        if not command:
            return ToolResult(success=False, error="缺少必要参数: command")

        timeout_sec = min(timeout_ms, self.MAX_TIMEOUT) / 1000.0

        # 延迟检测：首次调用时查找可用的 bash
        _ensure_bash_detected()

        try:
            cwd = workdir or os.getcwd()

            if _BASH_PATH:
                # Windows + bash: 用 exec 方式调用，显式传 -c
                proc = await asyncio.create_subprocess_exec(
                    _BASH_PATH, "-c", command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
            else:
                # 原生 shell（Linux/Mac 的 sh，Windows 的 cmd）
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_sec
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    error=f"命令执行超时 ({timeout_ms}ms): {command[:100]}",
                )

            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": stdout_str[:100_000],  # 限制输出大小
                    "stderr": stderr_str[:100_000],
                    "exit_code": proc.returncode,
                    "timeout_ms": timeout_ms,
                },
                error=(
                    f"命令退出码: {proc.returncode}"
                    if proc.returncode != 0
                    else None
                ),
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error=f"Shell 不可用或命令未找到: {command[:100]}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"执行命令失败: {str(e)}",
            )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的 Shell 命令",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": f"超时时间（毫秒），默认 {self.DEFAULT_TIMEOUT}，最大 {self.MAX_TIMEOUT}",
                            "default": self.DEFAULT_TIMEOUT,
                        },
                        "workdir": {
                            "type": "string",
                            "description": "命令执行的工作目录，默认为当前目录",
                        },
                    },
                    "required": ["command"],
                },
            },
        }
