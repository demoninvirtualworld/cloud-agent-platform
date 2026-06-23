# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cloud Agent Platform — 基于 Python 的 Agent 工具框架，对标 Claude Code 工具系统设计。当前处于**早期搭建阶段**：`tools/` 包骨架已完成，上层 Agent Runtime 待实现。

## Architecture

```
tools/          ← 当前 focus，工具系统
  base.py         BaseTool + ToolResult
  registry.py     ToolRegistry（注册/查找/枚举）
  *.py            具体工具（骨架，待实现 execute）
```

**核心模式**: 每个工具继承 `BaseTool`，统一通过 `ToolRegistry` 管理。工具返回 `ToolResult(success, data, error, metadata)`，供上层 Agent 统一消费。

- `get_schema()` 返回 JSON Schema，与 LLM function calling 兼容
- 注册表模式支持动态增删工具

## Tech Stack

- Python 3.14、openai、httpx、pydantic、python-dotenv

## Development

```bash
# 激活虚拟环境
source venv/Scripts/activate   # Git Bash
venv\Scripts\activate          # cmd/PowerShell

# 管理依赖
pip freeze > requirements.txt
pip install -r requirements.txt
```

当前无 build/lint/test 基础设施。项目无 `requirements.txt` 或 `pyproject.toml` — 依赖仅存在于 venv 中，需尽快固化。
