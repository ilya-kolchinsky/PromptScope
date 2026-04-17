"""
Common types for LLM clients.
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Parameter definition for a tool."""

    type: str
    description: Optional[str] = None
    enum: Optional[list[str]] = None
    items: Optional[dict] = None  # For array types
    properties: Optional[dict] = None  # For object types
    required: Optional[list[str]] = None  # For object types


class ToolDefinition(BaseModel):
    """Definition of a tool/function the model can call."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters


class ToolCall(BaseModel):
    """A tool call made by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result from executing a tool."""

    tool_call_id: str
    result: Any  # Will be JSON-serialized


class Message(BaseModel):
    """A message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None  # For tool result messages


class GenerateRequest(BaseModel):
    """Request to generate a response from the LLM."""

    system_prompt: str
    messages: list[Message]
    tools: Optional[list[ToolDefinition]] = None
    max_tokens: int = 1024
    temperature: float = 0.7


class GenerateResponse(BaseModel):
    """Response from the LLM."""

    content: str
    tool_calls: Optional[list[ToolCall]] = None
    finish_reason: str  # "stop", "tool_calls", "length", etc.
    usage: Optional[dict] = None
