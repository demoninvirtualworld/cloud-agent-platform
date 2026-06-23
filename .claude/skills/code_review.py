"""code-review 技能 — 检查代码质量、风格和潜在问题。"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# 技能元数据
name = "code-review"
description = "代码审查 — 检查 Python 代码风格、潜在 bug 和改进建议"


async def execute(args: str):
    """执行代码审查。

    Args:
        args: 可选的文件或目录路径（为空则扫描当前目录）
    """
    cwd = Path.cwd()
    target = Path(args) if args else cwd

    if not target.exists():
        return {
            "success": False,
            "error": f"路径不存在: {args}",
        }

    # 收集 Python 文件
    py_files = (
        list(target.rglob("*.py"))
        if target.is_dir()
        else [target]
    )
    # 排除 venv / __pycache__
    py_files = [
        f for f in py_files
        if "venv" not in str(f) and "__pycache__" not in str(f)
    ][:50]

    all_issues: List[Dict[str, Any]] = []
    stats = {"total_lines": 0, "total_functions": 0, "total_classes": 0}

    for filepath in py_files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            stats["total_lines"] += len(lines)

            # 统计函数和类
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("def "):
                    stats["total_functions"] += 1
                elif stripped.startswith("class "):
                    stats["total_classes"] += 1

            file_issues = _check_file(filepath, lines, cwd)
            if file_issues:
                all_issues.append({
                    "file": str(filepath.relative_to(cwd)),
                    "lines": len(lines),
                    "issues": file_issues,
                })
        except Exception:
            pass

    summary = _build_summary(len(py_files), all_issues, stats)

    return {
        "success": True,
        "data": {
            "files_checked": len(py_files),
            "issues_found": sum(len(f["issues"]) for f in all_issues),
            "files_with_issues": all_issues,
            "stats": stats,
            "summary": summary,
        },
    }


def _check_file(
    filepath: Path, lines: List[str], cwd: Path
) -> List[Dict[str, Any]]:
    """对单个文件执行所有检查。"""
    issues: List[Dict[str, Any]] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # 忽略空行和注释
        if not stripped or stripped.startswith("#"):
            continue

        # bare except
        if stripped == "except:":
            issues.append({
                "line": i,
                "severity": "warning",
                "type": "bare_except",
                "message": "避免使用裸 except:，应指定具体异常类型",
            })

        # 过宽的 except Exception
        if "except Exception" in stripped and ":" in stripped:
            issues.append({
                "line": i,
                "severity": "info",
                "type": "broad_except",
                "message": "考虑捕获更具体的异常类型而非 Exception",
            })

        # print 语句（仅在生产代码中建议使用 logging）
        if stripped.startswith("print(") and "test" not in str(filepath):
            pass  # 此处不报，CLI 工具允许 print

        # TODO / FIXME / HACK 注释
        if "TODO" in stripped or "FIXME" in stripped or "HACK" in stripped:
            issues.append({
                "line": i,
                "severity": "info",
                "type": "todo_marker",
                "message": f"发现标记: {stripped[:80]}",
            })

    # 文件长度检查
    if len(lines) > 500:
        issues.append({
            "line": 0,
            "severity": "info",
            "type": "file_length",
            "message": f"文件较长 ({len(lines)} 行)，考虑拆分为多个模块",
        })

    return issues


def _build_summary(
    total_files: int,
    all_issues: List[Dict[str, Any]],
    stats: Dict[str, int],
) -> str:
    """生成审查摘要。"""
    total_issues = sum(len(f["issues"]) for f in all_issues)
    files_with_issues = len(all_issues)

    parts = [
        f"📊 代码审查完成 — 检查了 {total_files} 个文件",
        f"   {stats['total_lines']} 行代码, "
        f"{stats['total_functions']} 个函数, "
        f"{stats['total_classes']} 个类",
    ]

    if total_issues == 0:
        parts.append("   ✅ 未发现问题！")
    else:
        parts.append(
            f"   ⚠️ 发现 {total_issues} 个潜在问题 "
            f"（分布在 {files_with_issues} 个文件中）"
        )

    return "\n".join(parts)
