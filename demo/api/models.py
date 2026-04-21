"""
API request/response models.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# Request models

class PostMessageRequest(BaseModel):
    author: str = Field(description="Username of message author")
    content: str = Field(description="Message content")
    addressed_to: Optional[str] = Field(default=None, description="For assistant messages: which principal it's for")


class EditMessageRequest(BaseModel):
    editor: str = Field(description="Username of editor")
    new_content: str = Field(description="Updated message content")


class DeleteMessageRequest(BaseModel):
    deleter: str = Field(description="Username of deleter")


class AskAssistantRequest(BaseModel):
    principal: str = Field(description="User asking the question")
    query: str = Field(description="Question for the assistant")
    protected_mode: bool = Field(description="Whether to use protected mode")


class SearchRequest(BaseModel):
    principal: str = Field(description="User performing the search")
    query: str = Field(description="Search query")
    context_chars: int = Field(default=100, description="Characters of context around matches")


class GetContextRequest(BaseModel):
    principal: str = Field(description="User requesting context")
    logical_msg_id: str = Field(description="Target message ID")
    before: int = Field(default=2, description="Messages before")
    after: int = Field(default=2, description="Messages after")


# Response models

class MessageResponse(BaseModel):
    logical_msg_id: str
    author: str
    content: str
    created_at: str
    last_modified_at: str
    is_deleted: bool


class ProjectionResponse(BaseModel):
    principal: str
    effective_control_context: list[MessageResponse]
    visible_observation_context: list[MessageResponse]


class PromptDebugResponse(BaseModel):
    system_prompt: str
    messages: list[dict[str, str]]
    debug_info: str
    formatted_display: str


class AssistantResponse(BaseModel):
    principal: str
    query: str
    response: str
    protected_mode: bool
    prompt_debug: PromptDebugResponse


class SearchHitResponse(BaseModel):
    message: MessageResponse
    snippet: str
    match_positions: list[int]


class SearchResultsResponse(BaseModel):
    query: str
    principal: str
    hits: list[SearchHitResponse]
    total_searched: int


class StatusResponse(BaseModel):
    status: str
    message_count: int
    event_count: int
