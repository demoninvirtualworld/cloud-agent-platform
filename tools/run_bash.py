"""执行 Bash 命令工具。"""

import asyncio
import os
import platform
import time
from typing import Any, Dict

from .base import BaseTool, ToolResult


class RunBashTool(BaseTool):
    name = "run_bash"
    description = "在终端中执行 Shell 命令并返回结果"

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

        try:
            # 构建子进程
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir or os.getcwd(),
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
