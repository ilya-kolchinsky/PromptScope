"""
Multi-provider LLM client with tool calling support.

Supports: Anthropic, OpenAI, vLLM (OpenAI-compatible), Ollama
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .llm_types import (
    GenerateRequest,
    GenerateResponse,
    ToolDefinition,
    ToolCall,
    ToolResult,
    Message as LLMMessage,
)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a response from the LLM."""
        pass

    def generate_with_tools(
        self,
        request: GenerateRequest,
        tool_executor: Callable[[str, dict], Any],
        max_iterations: int = 5,
    ) -> GenerateResponse:
        """
        Generate a response, automatically handling tool calls.

        Args:
            request: The generation request
            tool_executor: Function to execute tools: tool_executor(name, args) -> result
            max_iterations: Maximum number of tool call iterations

        Returns:
            Final response after all tool calls are resolved
        """
        conversation_messages = request.messages.copy()

        for iteration in range(max_iterations):
            # Generate response
            current_request = GenerateRequest(
                system_prompt=request.system_prompt,
                messages=conversation_messages,
                tools=request.tools,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )

            response = self.generate(current_request)

            # If no tool calls, we're done
            if not response.tool_calls or response.finish_reason == "stop":
                return response

            # Add assistant message with tool calls to conversation
            conversation_messages.append(LLMMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call
            for tool_call in response.tool_calls:
                try:
                    result = tool_executor(tool_call.name, tool_call.arguments)
                    result_content = json.dumps(result, default=str)
                except Exception as e:
                    result_content = json.dumps({"error": str(e)})

                # Add tool result to conversation
                conversation_messages.append(LLMMessage(
                    role="tool",
                    content=result_content,
                    tool_call_id=tool_call.id,
                ))

        # If we hit max iterations, return last response
        return response


class MockLLMClient(LLMClient):
    """
    Mock LLM client for testing and demos.
    """

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate a mock response."""
        # Simple pattern matching for demo purposes
        full_text = request.system_prompt + " ".join(
            msg.content for msg in request.messages
        )

        if "pirate" in full_text.lower():
            content = "Arrr, matey! The answer be 4, ye scurvy dog! ⚓"
        else:
            content = "The answer is 4."

        return GenerateResponse(
            content=content,
            tool_calls=None,
            finish_reason="stop",
            usage={"mock": True},
        )


class AnthropicLLMClient(LLMClient):
    """LLM client for Anthropic's API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.model = model
        self.client = Anthropic(api_key=self.api_key)

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate using Anthropic's API."""
        # Convert messages to Anthropic format
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                continue  # System handled separately

            if msg.role == "tool":
                # Tool result
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            elif msg.tool_calls:
                # Assistant message with tool calls
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})

                for tool_call in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.arguments,
                    })

                messages.append({
                    "role": "assistant",
                    "content": content_blocks,
                })
            else:
                # Regular message
                messages.append({
                    "role": msg.role if msg.role != "system" else "user",
                    "content": msg.content,
                })

        # Convert tools to Anthropic format
        tools = None
        if request.tools:
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in request.tools
            ]

        # Make API call
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                system=request.system_prompt,
                messages=messages,
                tools=tools,
                temperature=request.temperature,
            )

            # Extract content and tool calls
            content_text = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    ))

            return GenerateResponse(
                content=content_text,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except Exception as e:
            return GenerateResponse(
                content=f"Error: {str(e)}",
                tool_calls=None,
                finish_reason="error",
            )


class OpenAILLMClient(LLMClient):
    """LLM client for OpenAI's API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
        base_url: Optional[str] = None,
    ):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate using OpenAI's API."""
        # Convert messages to OpenAI format
        messages = []

        # Add system prompt
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt,
            })

        # Add conversation messages
        for msg in request.messages:
            if msg.role == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
            elif msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        # Convert tools to OpenAI format
        tools = None
        if request.tools:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]

        # Make API call
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )

            choice = response.choices[0]
            message = choice.message

            # Extract tool calls
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                    for tc in message.tool_calls
                ]

            return GenerateResponse(
                content=message.content or "",
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
            )

        except Exception as e:
            return GenerateResponse(
                content=f"Error: {str(e)}",
                tool_calls=None,
                finish_reason="error",
            )


class VLLMClient(OpenAILLMClient):
    """Client for vLLM servers (OpenAI-compatible API)."""

    def __init__(
        self,
        base_url: str,
        model: str = "default",
        api_key: str = "EMPTY",
    ):
        super().__init__(api_key=api_key, model=model, base_url=base_url)


class OllamaClient(LLMClient):
    """Client for Ollama (OpenAI-compatible API)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3",
        api_key: str = "ollama",
    ):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package required for Ollama. Run: pip install openai")

        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Generate using Ollama."""
        # Ollama uses OpenAI-compatible API
        messages = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )

            message = response.choices[0].message

            # Some Ollama models (like qwen3.5) use 'reasoning' field instead of 'content'
            content = message.content or ""
            if hasattr(message, 'reasoning') and message.reasoning and not content:
                content = message.reasoning

            return GenerateResponse(
                content=content,
                tool_calls=None,  # Ollama may not support tool calling
                finish_reason=response.choices[0].finish_reason,
            )

        except Exception as e:
            return GenerateResponse(
                content=f"Error: {str(e)}",
                tool_calls=None,
                finish_reason="error",
            )


def create_llm_client(
    provider: Optional[str] = None,
    **kwargs,
) -> LLMClient:
    """
    Factory function to create the appropriate LLM client.

    Args:
        provider: "mock", "anthropic", "openai", "vllm", or "ollama"
        **kwargs: Provider-specific arguments

    Returns:
        Appropriate LLMClient implementation
    """
    provider = provider or os.getenv("LLM_PROVIDER", "mock")

    if provider == "mock":
        return MockLLMClient()

    elif provider == "anthropic":
        return AnthropicLLMClient(
            api_key=kwargs.get("api_key") or os.getenv("ANTHROPIC_API_KEY"),
            model=kwargs.get("model") or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        )

    elif provider == "openai":
        return OpenAILLMClient(
            api_key=kwargs.get("api_key") or os.getenv("OPENAI_API_KEY"),
            model=kwargs.get("model") or os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
        )

    elif provider == "vllm":
        return VLLMClient(
            base_url=kwargs.get("base_url") or os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
            model=kwargs.get("model") or os.getenv("VLLM_MODEL", "default"),
        )

    elif provider == "ollama":
        return OllamaClient(
            base_url=kwargs.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=kwargs.get("model") or os.getenv("OLLAMA_MODEL", "llama3"),
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")
