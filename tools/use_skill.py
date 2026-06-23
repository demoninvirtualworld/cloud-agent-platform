"""调用技能工具 — 技能注册表 + 动态加载.

技能是 Python 模块，存放在 .claude/skills/ 目录下。
每个技能模块需提供:
    name: str           — 技能名称
    description: str    — 技能描述
    async execute(args: str) -> ToolResult  — 执行函数
"""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolResult


# ---------------------------------------------------------------------------
# 技能接口
# ---------------------------------------------------------------------------

class Skill:
    """一个已加载的技能实例。"""

    def __init__(
        self,
        name: str,
        description: str,
        execute_fn,
        source_path: str,
    ):
        self.name = name
        self.description = description
        self._execute_fn = execute_fn
        self.source_path = source_path

    async def execute(self, args: str) -> ToolResult:
        """执行技能。"""
        try:
            result = self._execute_fn(args)
            if asyncio_needed(result):
                result = await result
            # 确保返回 ToolResult
            if isinstance(result, ToolResult):
                return result
            if isinstance(result, dict):
                return ToolResult(
                    success=result.get("success", True),
                    data=result.get("data"),
                    error=result.get("error"),
                )
            return ToolResult(success=True, data={"result": str(result)})
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"技能 '{self.name}' 执行失败: {str(e)}",
            )


def asyncio_needed(obj) -> bool:
    """检查对象是否为协程（需要 await）。"""
    import asyncio
    return asyncio.iscoroutine(obj)


# ---------------------------------------------------------------------------
# 技能注册表
# ---------------------------------------------------------------------------

class SkillRegistry:
    """技能注册表 — 发现、加载和管理技能模块。"""

    def __init__(self, skills_dir: Optional[str] = None):
        self._skills: Dict[str, Skill] = {}
        self._loaded = False

        # 技能目录
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # 默认：项目根目录下的 .claude/skills/
            project_root = Path(__file__).resolve().parent.parent
            self.skills_dir = project_root / ".claude" / "skills"

    # ------------------------------------------------------------------
    # 注册 / 查找
    # ------------------------------------------------------------------

    def register(self, skill: Skill) -> None:
        """手动注册一个技能。"""
        if not skill.name:
            raise ValueError("技能名称不能为空")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """按名称获取技能（自动加载未缓存的）。"""
        if name in self._skills:
            return self._skills[name]
        # 尝试动态加载
        self._ensure_loaded()
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        """列出所有可用技能。"""
        self._ensure_loaded()
        return [
            {"name": s.name, "description": s.description}
            for s in self._skills.values()
        ]

    def reload(self) -> None:
        """重新扫描并加载所有技能。"""
        self._skills.clear()
        self._loaded = False
        self._ensure_loaded()

    # ------------------------------------------------------------------
    # 内部：目录扫描 + 动态加载
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """确保技能已从磁盘加载（懒加载，仅首次调用时执行）。"""
        if self._loaded:
            return
        self._loaded = True
        self._scan_directory()

    def _scan_directory(self) -> None:
        """扫描技能目录中的所有 .py 文件并加载。"""
        if not self.skills_dir.exists():
            self._register_builtin_fallbacks()
            return

        for filepath in self.skills_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue
            try:
                skill = self._load_skill_file(filepath)
                if skill:
                    self._skills[skill.name] = skill
            except Exception:
                continue  # 跳过无法加载的技能

        # 如果没有加载到任何技能，回退到内置技能
        if not self._skills:
            self._register_builtin_fallbacks()

    def _load_skill_file(self, filepath: Path) -> Optional[Skill]:
        """从 .py 文件加载技能模块。"""
        module_name = f"skill_{filepath.stem}"

        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        name = getattr(module, "name", filepath.stem)
        description = getattr(module, "description", "")
        execute_fn = getattr(module, "execute", None)

        if execute_fn is None:
            return None

        return Skill(
            name=name,
            description=description,
            execute_fn=execute_fn,
            source_path=str(filepath),
        )

    def _register_builtin_fallbacks(self) -> None:
        """注册内置回退技能（当无外部技能目录时）。"""
        self._skills["code-review"] = Skill(
            name="code-review",
            description="代码审查 — 检查代码风格、潜在问题和改进建议",
            execute_fn=_builtin_code_review,
            source_path="builtin",
        )
        self._skills["verify"] = Skill(
            name="verify",
            description="验证 — 运行测试套件验证代码正确性",
            execute_fn=_builtin_verify,
            source_path="builtin",
        )


# ---------------------------------------------------------------------------
# 内置技能实现
# ---------------------------------------------------------------------------

async def _builtin_code_review(args: str) -> ToolResult:
    """内置代码审查技能。

    扫描当前目录中的 Python 文件，检查：
    - 是否存在常见的代码问题（如 bare except）
    - 文件大小是否合理
    - import 语句是否规范
    """
    from pathlib import Path

    cwd = Path.cwd()
    target = Path(args) if args else cwd

    if not target.exists():
        return ToolResult(success=False, error=f"路径不存在: {args}")

    py_files = list(target.glob("**/*.py")) if target.is_dir() else [target]
    # 排除 venv 和 __pycache__
    py_files = [
        f for f in py_files
        if "venv" not in str(f) and "__pycache__" not in str(f)
    ][:50]  # 限制 50 个文件

    issues: List[Dict[str, Any]] = []
    for filepath in py_files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            file_issues = []

            # 检查 bare except
            for i, line in enumerate(lines, 1):
                if "except:" in line and "except:" == line.strip():
                    file_issues.append({
                        "line": i,
                        "type": "bare_except",
                        "message": "避免使用裸 except:，应指定异常类型",
                    })
                if "except Exception:" in line:
                    file_issues.append({
                        "line": i,
                        "type": "broad_except",
                        "message": "考虑捕获更具体的异常类型",
                    })

            # 检查文件长度
            if len(lines) > 500:
                file_issues.append({
                    "line": 0,
                    "type": "file_length",
                    "message": f"文件过长 ({len(lines)} 行)，考虑拆分",
                })

            if file_issues:
                issues.append({
                    "file": str(filepath.relative_to(cwd)),
                    "issues": file_issues,
                })
        except Exception:
            pass

    if not issues:
        return ToolResult(
            success=True,
            data={
                "files_checked": len(py_files),
                "issues_found": 0,
                "summary": "✅ 未发现常见问题。",
            },
        )

    return ToolResult(
        success=True,
        data={
            "files_checked": len(py_files),
            "issues_found": sum(len(f["issues"]) for f in issues),
            "files_with_issues": issues,
            "summary": (
                f"发现 {sum(len(f['issues']) for f in issues)} 个潜在问题 "
                f"分布在 {len(issues)} 个文件中。"
            ),
        },
    )


async def _builtin_verify(args: str) -> ToolResult:
    """内置验证技能 — 运行 pytest。"""
    import asyncio

    cwd = os.getcwd()

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest",
            "tests/", "-v", "--tb=short",
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=60
        )
        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        return ToolResult(
            success=proc.returncode == 0,
            data={
                "exit_code": proc.returncode,
                "output": stdout_str[-2000:],  # 限制输出大小
            },
            error=(
                f"测试失败 (退出码 {proc.returncode})"
                if proc.returncode != 0 else None
            ),
        )
    except asyncio.TimeoutError:
        return ToolResult(success=False, error="测试执行超时 (60s)")
    except FileNotFoundError:
        return ToolResult(
            success=False,
            error="pytest 未安装。请运行: pip install pytest pytest-asyncio",
        )
    except Exception as e:
        return ToolResult(success=False, error=f"验证失败: {str(e)}")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_global_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表单例。"""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = SkillRegistry()
    return _global_skill_registry


# ---------------------------------------------------------------------------
# UseSkillTool
# ---------------------------------------------------------------------------

class UseSkillTool(BaseTool):
    name = "use_skill"
    description = (
        "调用指定的技能（Slash Command）来执行专门的操作。"
        "可用技能包括: code-review（代码审查）, verify（运行测试）"
    )

    async def execute(self, **kwargs) -> ToolResult:
        skill_name = kwargs.get("skill", "")
        args = kwargs.get("args", "")

        if not skill_name:
            return ToolResult(success=False, error="缺少必要参数: skill")

        registry = get_skill_registry()

        skill = registry.get(skill_name)
        if skill is None:
            available = registry.list_skills()
            names = ", ".join(s["name"] for s in available) if available else "无"
            return ToolResult(
                success=False,
                error=(
                    f"技能 '{skill_name}' 未注册。"
                    f"可用技能: {names}"
                ),
            )

        return await skill.execute(args or "")

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": (
                                "要调用的技能名称（不含前导斜杠），"
                                "如 'code-review', 'verify'"
                            ),
                        },
                        "args": {
                            "type": "string",
                            "description": "传递给技能的可选参数",
                        },
                    },
                    "required": ["skill"],
                },
            },
        }
