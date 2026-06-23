"""verify 技能 — 运行测试套件验证代码正确性。"""

import asyncio
import os
import sys

# 技能元数据
name = "verify"
description = "验证 — 运行 pytest 测试套件检查代码正确性"


async def execute(args: str):
    """执行测试验证。

    Args:
        args: 可选的 pytest 参数（如 'tests/test_tools_base.py -v'）
    """
    cwd = os.getcwd()

    # 构建 pytest 命令
    cmd_args = [sys.executable, "-m", "pytest"]
    if args:
        cmd_args.extend(args.split())
    else:
        cmd_args.extend(["tests/", "-v", "--tb=short"])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=60
        )

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        # 提取测试摘要
        summary = _extract_summary(stdout_str)

        return {
            "success": proc.returncode == 0,
            "data": {
                "exit_code": proc.returncode,
                "summary": summary,
                "output": stdout_str[-3000:],
            },
            "error": (
                f"测试失败 (退出码 {proc.returncode})"
                if proc.returncode != 0 else None
            ),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "测试执行超时 (60s)",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "pytest 未安装。请运行: pip install pytest pytest-asyncio",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"验证失败: {str(e)}",
        }


def _extract_summary(output: str) -> str:
    """从 pytest 输出中提取摘要行。"""
    lines = output.strip().split("\n")
    # 查找最后几行包含摘要的行
    summary_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if any(kw in stripped for kw in [
            "passed", "failed", "error", "warning",
            "===", "...",
        ]):
            summary_lines.insert(0, stripped)
        else:
            break
    return "\n".join(summary_lines) if summary_lines else output[-500:]
