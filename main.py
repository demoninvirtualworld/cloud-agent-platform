#!/usr/bin/env python3
"""
DScode — CLI 入口
=================
基于 Python 的 AI Agent 工具框架，提供交互式对话代理与会话管理功能。

用法:
    DScode create [选项]    创建新会话并启动代理
    DScode list             列出所有已保存的会话
    DScode resume --id ID   恢复指定会话
    DScode delete --id ID   删除指定会话
    DScode version          显示版本信息
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，确保在任何目录下运行时都能找到本地模块
# （如 config, agent, ui, tools, session, llmapi 等）
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import check_llm_config


# ---------------------------------------------------------------------------
# 编码兼容性
# ---------------------------------------------------------------------------

def _setup_encoding() -> None:
    """确保 stdout/stderr 使用 UTF-8 编码，避免 Windows GBK 终端乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 版本信息
# ---------------------------------------------------------------------------

VERSION = "0.1.0"
DESCRIPTION = "DScode — Python AI Agent 工具框架"


# ---------------------------------------------------------------------------
# 工具注册工厂
# ---------------------------------------------------------------------------

def create_default_registry():
    """
    创建并初始化默认的 ToolRegistry，注册所有可用工具。

    每个工具目前仅有骨架（execute / get_schema 未实现），
    后续逐步补全各工具的实际逻辑。
    """
    from tools.registry import ToolRegistry

    # 导入所有工具类
    from tools.ask_user import AskUserTool
    from tools.create_cron import CreateCronTool
    from tools.edit_file import EditFileTool
    from tools.enter_plan_mode import EnterPlanModeTool
    from tools.glob_search import GlobSearchTool
    from tools.grep_search import GrepSearchTool
    from tools.read_file import ReadFileTool
    from tools.run_bash import RunBashTool
    from tools.run_workflow import RunWorkflowTool
    from tools.start_agent import StartAgentTool
    from tools.task_create import TaskCreateTool
    from tools.task_update import TaskUpdateTool
    from tools.use_skill import UseSkillTool
    from tools.web_fetch import WebFetchTool
    from tools.web_search import WebSearchTool
    from tools.write_file import WriteFileTool

    registry = ToolRegistry()

    # 注册所有工具
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(RunBashTool())
    registry.register(GlobSearchTool())
    registry.register(GrepSearchTool())
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(StartAgentTool())
    registry.register(AskUserTool())
    registry.register(TaskCreateTool())
    registry.register(TaskUpdateTool())
    registry.register(UseSkillTool())
    registry.register(EnterPlanModeTool())
    registry.register(CreateCronTool())
    registry.register(RunWorkflowTool())

    return registry


# ---------------------------------------------------------------------------
# 环境检查
# ---------------------------------------------------------------------------

def check_environment() -> str | None:
    """
    验证必要的 config.json 配置是否完整。

    Returns:
        如果缺少必要配置则返回错误消息，否则返回 None。
    """
    return check_llm_config()


# ---------------------------------------------------------------------------
# 命令处理器
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> None:
    """创建新会话并启动交互式代理。"""
    error = check_environment()
    if error:
        print(f"❌ {error}")
        sys.exit(1)

    from agent.agent import Agent

    registry = create_default_registry()

    agent = Agent(
        name=args.name,
        max_turns=args.max_turns,
        tool_registry=registry,
        effort=args.effort,
    )

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n\n👋 会话已中断。")


def cmd_list(args: argparse.Namespace) -> None:
    """列出所有已保存的会话。"""
    from session.manager import SessionManager

    session_manager = SessionManager()
    sessions = session_manager.list_sessions()

    if not sessions:
        print("📭 没有已保存的会话。")
        return

    # 表头
    header = f"{'ID':<14} {'名称':<24} {'轮数':<8} {'消息数':<8} {'更新时间'}"
    print(f"\n📋 已保存的会话 ({len(sessions)}):")
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for s in sessions:
        # 截取时间戳的可读部分
        updated = s.get("updated_at", "")[:19]
        print(
            f"{s['id']:<14} "
            f"{s['name'][:22]:<24} "
            f"{s['turn_count']:<8} "
            f"{s['message_count']:<8} "
            f"{updated}"
        )
    print("-" * len(header))


def cmd_resume(args: argparse.Namespace) -> None:
    """恢复已有会话并继续对话。"""
    error = check_environment()
    if error:
        print(f"❌ {error}")
        sys.exit(1)

    from agent.agent import Agent
    from session.manager import SessionManager

    session_manager = SessionManager()

    if not session_manager.session_exists(args.id):
        print(f"❌ 会话 {args.id} 不存在。使用 'list' 命令查看所有会话。")
        sys.exit(1)

    session = session_manager.load(args.id)
    if session is None:
        print(f"❌ 无法加载会话 {args.id}（文件可能已损坏）。")
        sys.exit(1)

    registry = create_default_registry()

    agent = Agent(
        name=session.agent_name,
        max_turns=session.max_turns,
        tool_registry=registry,
        effort=args.effort,
    )

    # 恢复会话历史：用已保存的消息替换初始 messages（只含 system prompt）
    restored_messages = session.to_api_messages()
    if restored_messages:
        # 保留 system prompt（位于 messages[0]），其余用历史消息替换
        agent.messages = [agent.messages[0]] + restored_messages
    agent.turn_count = session.turn_count

    print(f"📂 已恢复会话: {session.id} ({session.name})")
    print(f"   📜 已有 {len(restored_messages)} 条消息, {session.turn_count} 轮对话")

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n\n👋 会话已中断。")


def cmd_delete(args: argparse.Namespace) -> None:
    """删除指定会话。"""
    from session.manager import SessionManager

    session_manager = SessionManager()

    if not session_manager.session_exists(args.id):
        print(f"❌ 会话 {args.id} 不存在。")
        sys.exit(1)

    # 显示会话摘要便于确认
    session = session_manager.load(args.id)
    if session:
        print(f"🗑️  将删除会话: {session.id} ({session.name})")
        print(f"   消息数: {len(session.messages)}, 轮数: {session.turn_count}")

    session_manager.delete(args.id)
    print(f"✅ 会话 {args.id} 已删除。")


def cmd_version(args: argparse.Namespace) -> None:
    """显示版本信息。"""
    print(f"DScode v{VERSION}")
    print(f"Python {sys.version}")


# ---------------------------------------------------------------------------
# CLI 构建
# ------------------------------------------------
# ---------------------------

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="DScode",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  DScode                        启动交互式对话
  DScode create                 创建新会话
  DScode create --name my-agent --effort medium
  DScode list                   列出会话
  DScode resume --id abc123def456  恢复会话
  DScode delete --id abc123def456  删除会话
  DScode version                显示版本信息
        """,
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"DScode v{VERSION}"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ---- create ----
    create_parser = subparsers.add_parser("create", help="创建新会话")
    create_parser.add_argument(
        "--name", default="DScode", help="代理名称 (默认: DScode)"
    )
    create_parser.add_argument(
        "--session", default=None, help="会话名称 (默认: 自动生成)"
    )
    create_parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="最大对话轮数 (默认: 50)",
    )
    create_parser.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high"],
        help="LLM 思考力度 (默认: high)",
    )

    # ---- list ----
    subparsers.add_parser("list", help="列出所有已保存的会话")

    # ---- resume ----
    resume_parser = subparsers.add_parser("resume", help="恢复已有会话")
    resume_parser.add_argument(
        "--id", required=True, help="要恢复的会话 ID"
    )
    resume_parser.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high"],
        help="LLM 思考力度 (默认: high)",
    )

    # ---- delete ----
    delete_parser = subparsers.add_parser("delete", help="删除指定会话")
    delete_parser.add_argument(
        "--id", required=True, help="要删除的会话 ID"
    )

    # ---- version ----
    subparsers.add_parser("version", help="显示版本信息")

    return parser


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI 主入口。"""
    _setup_encoding()

    # 处理常见拼写错误：-version → --version
    if "-version" in sys.argv:
        sys.argv[sys.argv.index("-version")] = "--version"

    parser = build_parser()

    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse 在错误/帮助时抛出 SystemExit
        # Windows 下防止闪退：错误时暂停
        if e.code != 0:
            input("\n按 Enter 键退出...")
        raise

    # 无子命令时默认启动交互式对话
    if args.command is None:
        create_args = argparse.Namespace(
            name="DScode",
            session=None,
            max_turns=50,
            effort="high",
        )
        try:
            cmd_create(create_args)
        except (Exception, SystemExit) as e:
            if isinstance(e, SystemExit) and e.code == 0:
                raise
            if isinstance(e, SystemExit):
                print(f"\n❌ 启动失败 (错误码 {e.code})")
            else:
                print(f"\n❌ 启动失败: {e}")
            input("\n按 Enter 键退出...")
            sys.exit(1)
        return

    # 命令分发
    handlers = {
        "create": cmd_create,
        "list": cmd_list,
        "resume": cmd_resume,
        "delete": cmd_delete,
        "version": cmd_version,
    }

    handler = handlers.get(args.command)
    if handler:
        try:
            handler(args)
        except (Exception, SystemExit) as e:
            if isinstance(e, SystemExit) and e.code == 0:
                raise
            if isinstance(e, SystemExit):
                print(f"\n❌ 命令执行失败 (错误码 {e.code})")
            else:
                print(f"\n❌ 命令执行失败: {e}")
            input("\n按 Enter 键退出...")
            sys.exit(1)
    else:
        print(f"❌ 未知命令: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
