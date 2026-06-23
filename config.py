"""配置加载模块 — 从 config.json 读取 LLM 及其他配置。"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

# 项目根目录（无论从哪个目录运行，始终正确）
_PROJECT_ROOT = Path(__file__).resolve().parent
_CONFIG_PATH = _PROJECT_ROOT / "config.json"


def load_config() -> Dict[str, Any]:
    """加载 config.json 并返回完整配置字典。

    Returns:
        配置字典，如果文件不存在或格式错误则返回空字典。

    Raises:
        FileNotFoundError: config.json 不存在
        json.JSONDecodeError: JSON 格式错误
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {_CONFIG_PATH}\n"
            f"请复制 config.json.example 为 config.json 并填入配置信息。"
        )
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 相关配置。

    Returns:
        包含 model_id, api_key, base_url, timeout 的字典。
    """
    config = load_config()
    llm = config.get("llm", {})
    return {
        "model_id": llm.get("model_id", ""),
        "api_key": llm.get("api_key", ""),
        "base_url": llm.get("base_url", ""),
        "timeout": llm.get("timeout", 60),
    }


def check_llm_config() -> Optional[str]:
    """检查 LLM 配置是否完整。

    Returns:
        如果配置完整返回 None，否则返回错误消息。
    """
    try:
        llm = get_llm_config()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return str(e)

    missing = []
    if not llm["model_id"]:
        missing.append("llm.model_id")
    if not llm["api_key"]:
        missing.append("llm.api_key")
    if not llm["base_url"]:
        missing.append("llm.base_url")

    if missing:
        return (
            f"config.json 中缺少必要配置: {', '.join(missing)}\n"
            "请在 config.json 的 llm 段中配置:\n"
            '  "llm": {\n'
            '    "model_id": "your-model-id",\n'
            '    "api_key": "your-api-key",\n'
            '    "base_url": "https://api.example.com/v1",\n'
            '    "timeout": 60\n'
            "  }"
        )
    return None
