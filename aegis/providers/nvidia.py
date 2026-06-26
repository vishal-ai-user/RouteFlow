"""AEGIS NVIDIA NIM provider adapter.

Follows ARCHITECTURE.md §10 and NVIDIA_NIM_REFERENCE.md:
- Serializes InternalRequest to OpenAI-compatible payloads.
- Deserializes OpenAI-compatible responses to InternalResponse.
- Integrates with httpx.AsyncClient for non-blocking requests.
- Implements credentials-safe error normalization.
- Supports thinking block extraction (DeepSeek reasoning_content or <think> tags).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from aegis.core.errors import AegisError, ErrorType
from aegis.core.logging import get_logger
from aegis.core.schemas import (
    ContentBlockType,
    InternalRequest,
    InternalResponse,
    InternalResponseBlock,
    InternalUsage,
    StopReason,
)
from aegis.providers.base import BaseProvider

logger = get_logger(__name__)


class NvidiaProvider(BaseProvider):
    """NVIDIA NIM provider adapter implementing the BaseProvider contract."""

    async def complete(self, request: InternalRequest) -> InternalResponse:
        """Execute a non-streaming completion request to NVIDIA NIM."""
        url = self._build_endpoint_url()
        headers = self.get_headers()
        payload = self.serialize_request(request)

        logger.info(
            "Sending completion request to NVIDIA provider %s at %s. Model: %s",
            self.name,
            url,
            payload.get("model"),
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                response_data = response.json()
                return self.deserialize_response(response_data)

        except httpx.HTTPStatusError as exc:
            raise self._normalize_http_error(exc) from exc
        except httpx.TimeoutException as exc:
            logger.error("NVIDIA provider request timed out: %s", self.name)
            raise AegisError(
                ErrorType.TIMEOUT,
                "NVIDIA provider request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            # Prevent leaking credentials by logging a generic connection issue
            logger.error(
                "NVIDIA provider connection failure on %s: %s",
                self.name,
                type(exc).__name__,
            )
            raise AegisError(
                ErrorType.PROVIDER_ERROR,
                f"NVIDIA provider connection failure: {type(exc).__name__}",
            ) from exc
        except AegisError:
            raise
        except Exception as exc:
            err_msg = self._redact_secrets(str(exc))
            logger.error(
                "Unexpected error in NVIDIA provider adapter %s: %s",
                self.name,
                err_msg,
            )
            raise AegisError(
                ErrorType.PROVIDER_ERROR,
                f"Unexpected provider adapter error: {err_msg}",
            ) from exc

    async def complete_stream(
        self, request: InternalRequest
    ) -> AsyncIterator[InternalResponseBlock]:
        """Execute a streaming completion request and yield response blocks.

        Accumulates streaming tool call chunks internally and yields the parsed
        TOOL_USE block when the stream is completed or the tool call ends.
        """
        url = self._build_endpoint_url()
        headers = self.get_headers()
        payload = self.serialize_request(request)
        payload["stream"] = True

        logger.info(
            "Sending streaming request to NVIDIA provider %s at %s. Model: %s",
            self.name,
            url,
            payload.get("model"),
        )

        # Buffers for tool calls
        # Key: tool_index (int), Value: dict of tool fields
        tool_buffers: dict[int, dict[str, Any]] = {}

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_seconds) as client,
                client.stream("POST", url, json=payload, headers=headers) as response,
            ):
                response.raise_for_status()

                async for line in response.iter_lines():
                    if not line:
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line.removeprefix("data:").strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("Failed to decode SSE chunk: %s", data_str)
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # 1. Handle Thinking / Reasoning Block
                    if "reasoning_content" in delta and delta["reasoning_content"]:
                        yield InternalResponseBlock(
                            type=ContentBlockType.THINKING,
                            thinking_text=delta["reasoning_content"],
                        )

                    # 2. Handle Text Content
                    if "content" in delta and delta["content"]:
                        yield InternalResponseBlock(
                            type=ContentBlockType.TEXT,
                            text=delta["content"],
                        )

                    # 3. Handle Tool Calls
                    if "tool_calls" in delta and delta["tool_calls"]:
                        for tool_call_delta in delta["tool_calls"]:
                            idx = tool_call_delta.get("index", 0)
                            if idx not in tool_buffers:
                                tool_buffers[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }

                            buf = tool_buffers[idx]
                            if "id" in tool_call_delta and tool_call_delta["id"]:
                                buf["id"] = tool_call_delta["id"]

                            func_delta = tool_call_delta.get("function", {})
                            if "name" in func_delta and func_delta["name"]:
                                buf["name"] = func_delta["name"]
                            if "arguments" in func_delta and func_delta["arguments"]:
                                buf["arguments"] += func_delta["arguments"]

            # After stream finishes, yield all buffered tool calls
            for idx, buf in sorted(tool_buffers.items()):
                if buf["name"]:
                    try:
                        parsed_input = json.loads(buf["arguments"]) if buf["arguments"] else {}
                    except json.JSONDecodeError:
                        parsed_input = {"raw_arguments": buf["arguments"]}

                    yield InternalResponseBlock(
                        type=ContentBlockType.TOOL_USE,
                        tool_use_id=buf["id"] or f"call_{idx}",
                        tool_name=buf["name"],
                        tool_input=parsed_input,
                    )

        except httpx.HTTPStatusError as exc:
            raise self._normalize_http_error(exc) from exc
        except httpx.TimeoutException as exc:
            logger.error("NVIDIA provider stream timed out: %s", self.name)
            raise AegisError(
                ErrorType.TIMEOUT,
                "NVIDIA provider request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "NVIDIA provider stream connection failure on %s: %s",
                self.name,
                type(exc).__name__,
            )
            raise AegisError(
                ErrorType.PROVIDER_ERROR,
                f"NVIDIA provider connection failure: {type(exc).__name__}",
            ) from exc
        except AegisError:
            raise
        except Exception as exc:
            err_msg = self._redact_secrets(str(exc))
            logger.error(
                "Unexpected error in NVIDIA provider stream %s: %s",
                self.name,
                err_msg,
            )
            raise AegisError(
                ErrorType.PROVIDER_ERROR,
                f"Unexpected provider adapter error: {err_msg}",
            ) from exc

    def get_headers(self) -> dict[str, str]:
        """Generate authentication and content-type headers for NVIDIA NIM."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def serialize_request(self, request: InternalRequest) -> dict[str, Any]:
        """Convert InternalRequest to NVIDIA-compatible OpenAI completion format."""
        # 1. Resolve model identifier
        provider_model = self.model_mapping.get(request.model, request.model)

        # 2. Build messages array
        messages: list[dict[str, Any]] = []

        # System prompt block consolidation
        if request.system:
            system_text = "\n".join(
                block.text
                for block in request.system
                if block.type == ContentBlockType.TEXT and block.text
            )
            if system_text:
                messages.append({"role": "system", "content": system_text})

        # Process conversation messages
        for msg in request.messages:
            if msg.role == "user":
                # Check for tool results or mixed blocks
                has_tool_result = any(b.type == ContentBlockType.TOOL_RESULT for b in msg.content)

                if has_tool_result:
                    # Sequential output to respect OpenAI's message constraints
                    for block in msg.content:
                        if block.type == ContentBlockType.TEXT and block.text:
                            messages.append({"role": "user", "content": block.text})
                        elif block.type == ContentBlockType.TOOL_RESULT:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": block.tool_result_id or "",
                                "content": block.tool_result_content or "",
                            })
                else:
                    # Simple text message content consolidation
                    user_text = "\n".join(
                        b.text for b in msg.content if b.type == ContentBlockType.TEXT and b.text
                    )
                    messages.append({"role": "user", "content": user_text})

            elif msg.role == "assistant":
                # Assistant messages can contain text, thinking, and tool calls
                tool_calls = []
                for block in msg.content:
                    if block.type == ContentBlockType.TOOL_USE:
                        tool_calls.append({
                            "id": block.tool_use_id or "",
                            "type": "function",
                            "function": {
                                "name": block.tool_name or "",
                                "arguments": json.dumps(block.tool_input or {}),
                            },
                        })

                # Combine text and thinking blocks (wrapped in <think> tags)
                content_parts = []
                for block in msg.content:
                    if block.type == ContentBlockType.THINKING and block.thinking_text:
                        content_parts.append(f"<think>{block.thinking_text}</think>")
                    elif block.type == ContentBlockType.TEXT and block.text:
                        content_parts.append(block.text)

                combined_content = "\n".join(content_parts) if content_parts else None

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if combined_content is not None:
                    assistant_msg["content"] = combined_content
                else:
                    # OpenAI requires content to be null or omitted when tool_calls is present
                    assistant_msg["content"] = None

                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls

                messages.append(assistant_msg)

        # 3. Construct base payload
        payload: dict[str, Any] = {
            "model": provider_model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        }

        # Optional sampling controls
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        # Tools mapping
        if request.tools:
            payload_tools = []
            for tool in request.tools:
                payload_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema,
                    },
                })
            payload["tools"] = payload_tools

            # Tool choice mapping
            if request.tool_choice:
                tc_type = request.tool_choice.get("type")
                if tc_type == "auto":
                    payload["tool_choice"] = "auto"
                elif tc_type == "any":
                    payload["tool_choice"] = "required"
                elif tc_type == "tool":
                    tool_name = request.tool_choice.get("name")
                    payload["tool_choice"] = {
                        "type": "function",
                        "function": {"name": tool_name},
                    }

        return payload

    def deserialize_response(self, response_data: dict[str, Any]) -> InternalResponse:
        """Convert NVIDIA OpenAI-compatible response JSON to InternalResponse."""
        resp_id = response_data.get("id") or "msg_unknown"
        model = response_data.get("model") or ""

        choices = response_data.get("choices", [])
        if not choices:
            raise AegisError(
                ErrorType.PROVIDER_ERROR,
                "Malformed provider response: choices array is empty.",
            )

        choice = choices[0]
        message = choice.get("message", {})
        content_str = message.get("content") or ""
        reasoning_content = message.get("reasoning_content") or ""
        tool_calls = message.get("tool_calls") or []
        finish_reason = choice.get("finish_reason") or "stop"

        content_blocks: list[InternalResponseBlock] = []

        # 1. Parse thinking / reasoning blocks
        if reasoning_content:
            content_blocks.append(
                InternalResponseBlock(
                    type=ContentBlockType.THINKING,
                    thinking_text=reasoning_content,
                )
            )
            if content_str:
                content_blocks.append(
                    InternalResponseBlock(
                        type=ContentBlockType.TEXT,
                        text=content_str,
                    )
                )
        else:
            # Fallback for models returning thinking inside <think> tags in the main content
            if content_str.startswith("<think>") and "</think>" in content_str:
                parts = content_str.split("</think>", 1)
                think_part = parts[0].removeprefix("<think>").strip()
                text_part = parts[1].strip()

                if think_part:
                    content_blocks.append(
                        InternalResponseBlock(
                            type=ContentBlockType.THINKING,
                            thinking_text=think_part,
                        )
                    )
                if text_part:
                    content_blocks.append(
                        InternalResponseBlock(
                            type=ContentBlockType.TEXT,
                            text=text_part,
                        )
                    )
            elif content_str:
                content_blocks.append(
                    InternalResponseBlock(
                        type=ContentBlockType.TEXT,
                        text=content_str,
                    )
                )

        # 2. Parse tool calls
        for tc in tool_calls:
            func = tc.get("function", {})
            func_args_str = func.get("arguments") or "{}"
            try:
                parsed_args = json.loads(func_args_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool call arguments JSON: %s", func_args_str)
                parsed_args = {"raw_arguments": func_args_str}

            content_blocks.append(
                InternalResponseBlock(
                    type=ContentBlockType.TOOL_USE,
                    tool_use_id=tc.get("id") or "call_unknown",
                    tool_name=func.get("name") or "unknown",
                    tool_input=parsed_args,
                )
            )

        # 3. Map finish reason to StopReason
        stop_reason = StopReason.END_TURN
        if finish_reason == "length":
            stop_reason = StopReason.MAX_TOKENS
        elif finish_reason == "tool_calls":
            stop_reason = StopReason.TOOL_USE
        elif finish_reason == "stop_sequence":
            stop_reason = StopReason.STOP_SEQUENCE

        # 4. Map token usage
        usage_data = response_data.get("usage") or {}
        usage = InternalUsage(
            input_tokens=usage_data.get("prompt_tokens") or 0,
            output_tokens=usage_data.get("completion_tokens") or 0,
        )

        return InternalResponse(
            id=resp_id,
            role="assistant",
            content=content_blocks,
            model=model,
            stop_reason=stop_reason,
            usage=usage,
        )

    def _build_endpoint_url(self) -> str:
        """Construct the full completions endpoint URL."""
        url = self.base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return f"{url}/chat/completions"
        return f"{url}/v1/chat/completions"

    def _normalize_http_error(self, exc: httpx.HTTPStatusError) -> AegisError:
        """Convert httpx.HTTPStatusError to standard AegisError without leaking secrets."""
        status_code = exc.response.status_code
        try:
            err_json = exc.response.json()
            err_msg = err_json.get("error", {}).get("message") or exc.response.text
        except Exception:
            err_msg = exc.response.text or "Unknown HTTP error"

        # Redact any secrets and limit error length
        err_msg = self._redact_secrets(err_msg)[:500]

        logger.error(
            "NVIDIA provider request failed: status=%d, provider=%s, detail=%s",
            status_code,
            self.name,
            err_msg,
        )

        if status_code in (401, 403):
            return AegisError(
                ErrorType.UNAUTHORIZED,
                f"NVIDIA provider authentication failed: {err_msg}",
            )
        if status_code == 429:
            return AegisError(
                ErrorType.RATE_LIMITED,
                f"NVIDIA provider rate limit exceeded: {err_msg}",
            )
        if status_code in (400, 422):
            return AegisError(
                ErrorType.VALIDATION_ERROR,
                f"NVIDIA provider request validation failed: {err_msg}",
            )
        if status_code == 504:
            return AegisError(
                ErrorType.TIMEOUT,
                "NVIDIA provider request timed out.",
            )

        return AegisError(
            ErrorType.PROVIDER_ERROR,
            f"NVIDIA provider error ({status_code}): {err_msg}",
        )

    def _redact_secrets(self, text: str) -> str:
        """Replace occurrences of the secret API key with a redacted placeholder."""
        if not text or not self.api_key:
            return text
        return text.replace(self.api_key, "[REDACTED]")
