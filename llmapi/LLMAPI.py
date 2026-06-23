import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（从项目根目录查找）
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


class LLMAPI:
    """
    为 Cloud Agent Platform 定制的 LLM 客户端。
    兼容 OpenAI 接口，默认使用流式响应，返回结构化 dict。
    """

    def __init__(
        self,
        model: str = None,
        apiKey: str = None,
        baseUrl: str = None,
        timeout: int = None,
    ):
        """初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载。"""
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError(
                "模型ID、API密钥和服务地址必须被提供或在.env文件中定义。"
            )

        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout)

    def think(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0,
        tools: Optional[List[Dict[str, Any]]] = None,
        effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        调用大语言模型进行思考，返回结构化响应。

        Args:
            messages: 对话消息列表
            temperature: 采样温度
            tools: 工具的 JSON Schema 列表（用于 function calling）
            effort: 思考力度 ("low", "medium", "high")

        Returns:
            dict: {
                "finish_reason": str,      # "stop", "tool_calls", "length", etc.
                "content": Optional[str],   # 文本回复内容
                "reasoning_content": Optional[str],  # 推理链内容
                "tool_calls": Optional[List[dict]],  # 工具调用列表
            }
        """
        print(f"🧠 正在调用 {self.model} 模型...")

        # 构建请求参数
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        if effort:
            # 某些模型支持 extended thinking
            request_kwargs["extra_body"] = {
                "thinking": {"type": "enabled", "effort": effort}
            }

        try:
            response = self.client.chat.completions.create(**request_kwargs)

            # 累积流式响应
            collected_content: List[str] = []
            collected_reasoning: List[str] = []
            tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}
            finish_reason: Optional[str] = None

            for chunk in response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 累积文本内容
                if delta.content:
                    collected_content.append(delta.content)
                    print(delta.content, end="", flush=True)

                # 累积推理链内容（DeepSeek / extended thinking 模型）
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning is None and hasattr(delta, "model_extra"):
                    reasoning = (delta.model_extra or {}).get(
                        "reasoning_content", ""
                    )
                if reasoning:
                    collected_reasoning.append(reasoning)

                # 累积 tool_calls（流式返回为增量 delta，需按 index 聚合）
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_accumulator:
                            tool_calls_accumulator[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_accumulator[idx]
                        if tc.id:
                            entry["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                entry["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                entry["function"]["arguments"] += (
                                    tc.function.arguments
                                )

                # 捕获 finish_reason
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            print()  # 流式输出结束后换行

            # 构建 tool_calls 列表（按 index 排序）
            tool_calls_list = None
            if tool_calls_accumulator:
                tool_calls_list = [
                    tool_calls_accumulator[i]
                    for i in sorted(tool_calls_accumulator.keys())
                ]

            content = "".join(collected_content) or None
            reasoning_content = "".join(collected_reasoning) or None

            # 推断 finish_reason：某些 API 可能不发送 finish_reason
            # 但 tool_calls 已累积完成，此时应视为 tool_calls 而非 stop
            if finish_reason is None:
                finish_reason = "tool_calls" if tool_calls_list else "stop"

            if finish_reason == "stop" and content:
                print("✅ 大语言模型响应成功:")

            return {
                "finish_reason": finish_reason,
                "content": content,
                "reasoning_content": reasoning_content,
                "tool_calls": tool_calls_list,
            }

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return {
                "finish_reason": "error",
                "content": None,
                "reasoning_content": None,
                "tool_calls": None,
                "error": str(e),
            }
