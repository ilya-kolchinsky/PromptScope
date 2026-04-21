"""
FastAPI server for PromptScope demo.

This module provides the REST API for the PromptScope demo app,
showcasing the clean MultiUserSession API.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from promptscope import (
    MultiUserSession,
    Message,
    Projection,
    Response as LLMResponse,
    ValidationError,
    NotFoundError,
    ConfigurationError,
)

from .models import (
    PostMessageRequest,
    EditMessageRequest,
    DeleteMessageRequest,
    AskAssistantRequest,
    MessageResponse,
    ProjectionResponse,
    PromptDebugResponse,
    AssistantResponse,
    StatusResponse,
)
from .seed_data import initialize_demo_session


# Initialize global session
session: Optional[MultiUserSession] = None


def get_session() -> MultiUserSession:
    """Lazy initialization of the multi-user session."""
    global session
    if session is None:
        session = initialize_demo_session()
    return session


# Create FastAPI app
app = FastAPI(
    title="PromptScope Demo",
    description="A demo application showcasing PromptScope's multi-user LLM protection",
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
        logical_msg_id=msg.id,
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
    sess = get_session()
    messages = sess.get_messages()
    events = sess.event_log.get_all_events()

    return StatusResponse(
        status="ok",
        message_count=len(messages),
        event_count=len(events),
    )


@app.get("/api/messages")
async def get_messages() -> list[MessageResponse]:
    """Get all current messages."""
    sess = get_session()
    messages = sess.get_messages()
    return [message_to_response(msg) for msg in messages]


@app.post("/api/messages")
async def post_message(request: PostMessageRequest) -> MessageResponse:
    """Post a new message."""
    try:
        sess = get_session()
        msg = sess.post(request.author, request.content, request.addressed_to)
        return message_to_response(msg)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/messages/{message_id}")
async def edit_message(message_id: str, request: EditMessageRequest) -> MessageResponse:
    """Edit an existing message."""
    try:
        sess = get_session()
        msg = sess.edit_message(message_id, request.new_content, request.editor)
        return message_to_response(msg)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/messages/{message_id}")
async def delete_message(message_id: str, request: DeleteMessageRequest) -> dict:
    """Delete a message."""
    try:
        sess = get_session()
        sess.delete_message(message_id, request.deleter)
        return {"status": "deleted", "message_id": message_id}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projection/{principal}")
async def get_projection(principal: str) -> ProjectionResponse:
    """Get projection for a specific principal."""
    sess = get_session()
    projected_view = sess.get_projection(principal)

    return ProjectionResponse(
        principal=projected_view.principal,
        effective_control_context=[
            message_to_response(msg) for msg in projected_view.effective_control
        ],
        visible_observation_context=[
            message_to_response(msg) for msg in projected_view.visible_observation
        ],
    )


@app.post("/api/assistant/ask")
async def ask_assistant(request: AskAssistantRequest) -> AssistantResponse:
    """Ask the assistant a question."""
    try:
        sess = get_session()

        # Get LLM response
        response = sess.ask(
            principal=request.principal,
            query=request.query,
            protected_mode=request.protected_mode,
            include_debug_info=True,
        )

        # Build debug response
        debug_info = response.debug_info or {}
        prompt_debug = PromptDebugResponse(
            system_prompt=debug_info.get("system_prompt", ""),
            messages=debug_info.get("messages", []),
            debug_info=str(debug_info),
            formatted_display=str(debug_info),
        )

        return AssistantResponse(
            principal=response.principal,
            query=response.query,
            response=response.content,
            protected_mode=response.protected_mode,
            prompt_debug=prompt_debug,
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ACL Management Endpoints

@app.get("/api/acl/users")
async def get_all_users() -> dict:
    """Get all users."""
    try:
        sess = get_session()
        users = sess.list_users()
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
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/acl/groups")
async def get_all_groups() -> dict:
    """Get all groups."""
    try:
        sess = get_session()
        # Access user store directly (advanced use)
        groups = sess._user_store.get_all_groups()
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
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/acl/groups/{group_id}/members/{user_id}")
async def add_user_to_group(group_id: str, user_id: str) -> dict:
    """Add a user to a group."""
    try:
        sess = get_session()
        sess.add_to_group(user_id, group_id)
        return {
            "status": "success",
            "user_id": user_id,
            "group_id": group_id,
            "action": "added",
        }
    except (NotFoundError, ValidationError, ConfigurationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/acl/groups/{group_id}/members/{user_id}")
async def remove_user_from_group(group_id: str, user_id: str) -> dict:
    """Remove a user from a group."""
    try:
        sess = get_session()
        sess.remove_from_group(user_id, group_id)
        return {
            "status": "success",
            "user_id": user_id,
            "group_id": group_id,
            "action": "removed",
        }
    except (NotFoundError, ValidationError, ConfigurationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/acl/influence/{principal}")
async def get_influence_set(principal: str) -> dict:
    """Get all users who can influence this principal."""
    try:
        sess = get_session()
        influencers = sess.get_influencers(principal)
        return {
            "principal": principal,
            "influencers": list(influencers),
        }
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/reset")
async def reset_conversation() -> dict:
    """Reset the conversation to initial state."""
    global session
    session = None  # Will be re-initialized on next request
    return {"status": "reset"}


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
    return {"message": "PromptScope Demo API is running. UI not found."}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(app, host=host, port=port)
