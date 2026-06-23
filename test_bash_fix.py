"""
验证 run_bash.py 的修复 — 在纯 Windows CMD 环境下测试 WSL 存根检测。
此脚本不依赖任何 shell，只用 Python 验证逻辑。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# 强制清除旧缓存
import importlib
cache = os.path.join(
    os.path.dirname(__file__), "tools", "__pycache__", "run_bash.cpython-314.pyc"
)
if os.path.exists(cache):
    os.remove(cache)
    print("✅ 已清除旧 .pyc 缓存")

# 导入修复后的模块
from tools.run_bash import _is_wsl_stub, _verify_bash, _find_bash, _ensure_bash_detected

print("\n=== 测试 1: WSL 存根检测 ===")
wsl_path = r"C:\Windows\System32\bash.exe"
print(f"  {wsl_path!r} → is_wsl_stub = {_is_wsl_stub(wsl_path)}")

fake_git_bash = r"C:\Program Files\Git\usr\bin\bash.exe"
print(f"  {fake_git_bash!r} → is_wsl_stub = {_is_wsl_stub(fake_git_bash)}")

print("\n=== 测试 2: bash 查找（延迟检测）===")
_ensure_bash_detected()
from tools.run_bash import _BASH_PATH
if _BASH_PATH:
    print(f"  ✅ 找到可用 bash: {_BASH_PATH}")
else:
    print("  ⚠️  未找到真 bash，将使用 CMD 回退（符合预期）")

print("\n=== 测试 3: Shell 描述 ===")
from tools.run_bash import _get_shell_description, _SHELL_DESC
# 重置描述以触发重新生成
import tools.run_bash as rb
rb._SHELL_DESC = ""
desc = _get_shell_description()
print(f"  Shell 描述: {desc[:80]}...")

print("\n=== 测试 4: RunBashTool.execute() ===")
import asyncio
from tools.run_bash import RunBashTool

async def test():
    tool = RunBashTool()
    
    # 测试简单 Windows 命令
    result = await tool.execute(command="echo hello from Windows CMD")
    print(f"  echo 测试: success={result.success}")
    print(f"    stdout: {result.data.get('stdout', '')[:100] if result.data else 'N/A'}")
    print(f"    error:  {result.error}")
    
    # 测试 Python
    result = await tool.execute(command="python -c \"print('python works')\"")
    print(f"\n  python 测试: success={result.success}")
    print(f"    stdout: {result.data.get('stdout', '')[:100] if result.data else 'N/A'}")
    print(f"    error:  {result.error}")

asyncio.run(test())

print("\n✅ 全部验证完成")
