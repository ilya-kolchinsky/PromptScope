"""
FastAPI server for PromptScope.

This module provides the REST API for the PromptScope web app.
"""

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from promptscope.core.events import EventLog, MessagePosted, MessageEdited, MessageDeleted
from promptscope.core.conversation import ConversationState, Message
from promptscope.core.projection import ConversationProjector
from promptscope.core.prompt_builder import PromptBuilder
from promptscope.core.retrieval import ConversationRetrieval
from promptscope.core.retrieval_tools import ConversationTools, SearchFilters
from promptscope.core.llm_client import create_llm_client, LLMClient
from promptscope.core.acl import (
    ACLEvaluator,
    InMemoryPermissionStore,
    InMemoryUserStore,
)

from .models import (
    PostMessageRequest,
    EditMessageRequest,
    DeleteMessageRequest,
    AskAssistantRequest,
    SearchRequest,
    GetContextRequest,
    MessageResponse,
    ProjectionResponse,
    PromptDebugResponse,
    AssistantResponse,
    SearchResultsResponse,
    StatusResponse,
)
from .seed_data import load_seed_data, get_demo_users


# Initialize global state
event_log = EventLog()
conversation_state = ConversationState(event_log)

# Initialize ACL system
permission_store = InMemoryPermissionStore()
user_store = InMemoryUserStore()
acl_evaluator = ACLEvaluator(permission_store, user_store)

# Initialize projector with ACL
projector = ConversationProjector(conversation_state, acl_evaluator)
prompt_builder = PromptBuilder(conversation_state, projector)
retrieval = ConversationRetrieval(projector)
conversation_tools = ConversationTools(event_log, conversation_state, projector)
llm_client: Optional[LLMClient] = None

# Load seed data (including ACL data)
load_seed_data(event_log, user_store, permission_store)


def get_llm_client() -> LLMClient:
    """Lazy initialization of LLM client."""
    global llm_client
    if llm_client is None:
        llm_client = create_llm_client()
    return llm_client


# Create FastAPI app
app = FastAPI(
    title="PromptScope",
    description="A proof-of-concept for safe multi-user LLM chats",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions

def message_to_response(msg: Message) -> MessageResponse:
    """Convert Message to MessageResponse."""
    return MessageResponse(
        logical_msg_id=msg.logical_msg_id,
        author=msg.author,
        content=msg.content,
        created_at=msg.created_at.isoformat(),
        last_modified_at=msg.last_modified_at.isoformat(),
        is_deleted=msg.is_deleted,
    )


# API Endpoints

@app.get("/api/status")
async def get_status() -> StatusResponse:
    """Get server status."""
    messages = conversation_state.get_current_messages()
    events = event_log.get_all_events()

    return StatusResponse(
        status="ok",
        message_count=len(messages),
        event_count=len(events),
    )


@app.get("/api/users")
async def get_users() -> list[str]:
    """Get list of demo users."""
    return get_demo_users()


@app.get("/api/messages")
async def get_messages() -> list[MessageResponse]:
    """Get all current messages."""
    messages = conversation_state.get_current_messages()
    return [message_to_response(msg) for msg in messages]


@app.post("/api/messages")
async def post_message(request: PostMessageRequest) -> MessageResponse:
    """Post a new message."""
    logical_msg_id = str(uuid.uuid4())

    event = MessagePosted(
        logical_msg_id=logical_msg_id,
        author=request.author,
        content=request.content,
        addressed_to=request.addressed_to,
    )
    event_log.append(event)

    # Get the newly created message
    msg = conversation_state.get_message_by_id(logical_msg_id)
    if msg is None:
        raise HTTPException(status_code=500, detail="Failed to create message")

    return message_to_response(msg)


@app.put("/api/messages/{logical_msg_id}")
async def edit_message(
    logical_msg_id: str,
    request: EditMessageRequest,
) -> MessageResponse:
    """Edit an existing message."""
    # Check if message exists
    msg = conversation_state.get_message_by_id(logical_msg_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    event = MessageEdited(
        logical_msg_id=logical_msg_id,
        editor=request.editor,
        new_content=request.new_content,
    )
    event_log.append(event)

    # Get the updated message
    msg = conversation_state.get_message_by_id(logical_msg_id)
    if msg is None:
        raise HTTPException(status_code=500, detail="Failed to update message")

    return message_to_response(msg)


@app.delete("/api/messages/{logical_msg_id}")
async def delete_message(
    logical_msg_id: str,
    request: DeleteMessageRequest,
) -> dict:
    """Delete a message."""
    # Check if message exists
    msg = conversation_state.get_message_by_id(logical_msg_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    event = MessageDeleted(
        logical_msg_id=logical_msg_id,
        deleter=request.deleter,
    )
    event_log.append(event)

    return {"status": "deleted", "logical_msg_id": logical_msg_id}


@app.get("/api/projection/{principal}")
async def get_projection(principal: str) -> ProjectionResponse:
    """Get projection for a specific principal."""
    projected_view = projector.project_for_principal(principal)

    return ProjectionResponse(
        principal=projected_view.principal,
        effective_control_context=[
            message_to_response(msg)
            for msg in projected_view.effective_control_context
        ],
        visible_observation_context=[
            message_to_response(msg)
            for msg in projected_view.visible_observation_context
        ],
    )


@app.post("/api/assistant/ask")
async def ask_assistant(request: AskAssistantRequest) -> AssistantResponse:
    """Ask the assistant a question."""
    # Build the appropriate request based on mode
    if request.protected_mode:
        projected_view = projector.project_for_principal(request.principal)
        llm_request = prompt_builder.build_protected_request(
            request.principal,
            request.query,
            projected_view,
        )
    else:
        llm_request = prompt_builder.build_naive_request(
            request.principal,
            request.query,
        )

    # Create tool executor for this principal
    def tool_executor(tool_name: str, tool_args: dict):
        """Execute a retrieval tool."""
        if tool_name == "search_conversation":
            # Extract filters
            filters = None
            if any(k in tool_args for k in ["speakers", "time_range_start", "time_range_end"]):
                from datetime import datetime
                filters = SearchFilters(
                    speakers=tool_args.get("speakers"),
                    time_range_start=datetime.fromisoformat(tool_args["time_range_start"])
                    if tool_args.get("time_range_start") else None,
                    time_range_end=datetime.fromisoformat(tool_args["time_range_end"])
                    if tool_args.get("time_range_end") else None,
                )

            result = conversation_tools.search_conversation(
                principal=request.principal,
                query=tool_args["query"],
                filters=filters,
            )
            return result.model_dump()

        elif tool_name == "expand_local_context":
            result = conversation_tools.expand_local_context(
                principal=request.principal,
                hit_id=tool_args["hit_id"],
                window=tool_args.get("window", 2),
            )
            return result.model_dump()

        elif tool_name == "get_exact_event":
            result = conversation_tools.get_exact_event(
                principal=request.principal,
                event_id=tool_args["event_id"],
            )
            if result:
                return result.model_dump()
            return {"error": "Event not found"}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    # Get response from LLM
    client = get_llm_client()

    if request.protected_mode and llm_request.tools:
        # Use tool calling loop for protected mode
        llm_response = client.generate_with_tools(llm_request, tool_executor)
    else:
        # Simple generation for naïve mode
        llm_response = client.generate(llm_request)

    # Format request for debug display
    formatted_display = prompt_builder.format_request_for_display(
        llm_request,
        request.protected_mode,
        request.principal,
    )

    return AssistantResponse(
        principal=request.principal,
        query=request.query,
        response=llm_response.content,
        protected_mode=request.protected_mode,
        prompt_debug=PromptDebugResponse(
            system_prompt=llm_request.system_prompt,
            messages=[{"role": m.role, "content": m.content} for m in llm_request.messages],
            debug_info=formatted_display,
            formatted_display=formatted_display,
        ),
    )


@app.post("/api/retrieval/search")
async def search_messages(request: SearchRequest) -> SearchResultsResponse:
    """Search visible observation messages."""
    results = retrieval.search(
        request.principal,
        request.query,
        request.context_chars,
    )

    from .models import SearchHitResponse

    return SearchResultsResponse(
        query=results.query,
        principal=results.principal,
        hits=[
            SearchHitResponse(
                message=message_to_response(hit.message),
                snippet=hit.snippet,
                match_positions=hit.match_positions,
            )
            for hit in results.hits
        ],
        total_searched=results.total_searched,
    )


@app.post("/api/retrieval/context")
async def get_message_context(request: GetContextRequest) -> list[MessageResponse]:
    """Get surrounding context for a message."""
    context_messages = retrieval.get_message_context(
        request.principal,
        request.logical_msg_id,
        request.before,
        request.after,
    )

    return [message_to_response(msg) for msg in context_messages]


@app.post("/api/reset")
async def reset_conversation() -> dict:
    """Reset the conversation to seed state (removes user-added messages only)."""
    from .seed_data import SEED_MESSAGE_COUNT

    # Get all events
    all_events = event_log.get_all_events()

    # Keep only seed events
    seed_events = all_events[:SEED_MESSAGE_COUNT]

    # Clear and reload seed only
    event_log.clear()
    for event in seed_events:
        event_log.append(event)

    return {"status": "reset", "kept_messages": len(seed_events)}


# ACL Management Endpoints

@app.get("/api/acl/users")
async def get_all_users() -> dict:
    """Get all users."""
    users = user_store.get_all_users()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "groups": u.groups,
                "manager_id": u.manager_id,
            }
            for u in users
        ]
    }


@app.get("/api/acl/groups")
async def get_all_groups() -> dict:
    """Get all groups."""
    groups = user_store.get_all_groups()
    return {
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "members": g.members,
            }
            for g in groups
        ]
    }


@app.post("/api/acl/groups/{group_id}/members/{user_id}")
async def add_user_to_group(group_id: str, user_id: str) -> dict:
    """Add a user to a group."""
    success = user_store.add_user_to_group(user_id, group_id)
    if not success:
        raise HTTPException(status_code=404, detail="User or group not found")

    return {
        "status": "success",
        "user_id": user_id,
        "group_id": group_id,
        "action": "added",
    }


@app.delete("/api/acl/groups/{group_id}/members/{user_id}")
async def remove_user_from_group(group_id: str, user_id: str) -> dict:
    """Remove a user from a group."""
    success = user_store.remove_user_from_group(user_id, group_id)
    if not success:
        raise HTTPException(status_code=404, detail="User or group not found")

    return {
        "status": "success",
        "user_id": user_id,
        "group_id": group_id,
        "action": "removed",
    }


@app.get("/api/acl/influence/{principal}")
async def get_influence_set(principal: str) -> dict:
    """Get all users who can influence this principal."""
    influencers = acl_evaluator.get_influence_set(principal)
    return {
        "principal": principal,
        "influencers": list(influencers),
    }


# Serve static files
static_dir = Path(__file__).parent.parent / "ui" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index():
    """Serve the main UI."""
    index_path = Path(__file__).parent.parent / "ui" / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "PromptScope API is running. UI not found."}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(app, host=host, port=port)
