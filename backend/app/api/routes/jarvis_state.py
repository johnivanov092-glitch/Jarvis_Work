from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.jarvis_memory_sqlite import init_db, list_chats, create_chat, rename_chat, delete_chat, get_messages, add_message
from app.services.jarvis_settings_sqlite import get_settings, save_settings
from app.services.ollama_runtime_service import list_ollama_models

router = APIRouter(prefix="/api/jarvis", tags=["jarvis-state"])

class ChatCreateRequest(BaseModel):
    title: str = "Новый чат"

class ChatRenameRequest(BaseModel):
    title: str = Field(..., min_length=1)

class ChatMessageRequest(BaseModel):
    chat_id: int | None = None
    role: str = "user"
    content: str = Field(..., min_length=1)

class SettingsRequest(BaseModel):
    ollama_context: int = 8192
    default_model: str = "qwen3:8b"
    agent_profile: str = "Сбалансированный"

@router.on_event("startup")
def _startup():
    init_db()

@router.get("/models")
async def models():
    return await list_ollama_models()

@router.get("/settings")
def settings_get():
    init_db()
    return get_settings()

@router.put("/settings")
def settings_put(payload: SettingsRequest):
    init_db()
    return save_settings(payload.ollama_context, payload.default_model, payload.agent_profile)

@router.get("/chats")
def chats_list():
    init_db()
    return {"items": list_chats()}

@router.post("/chats")
def chats_create(payload: ChatCreateRequest):
    init_db()
    return create_chat(payload.title)

@router.patch("/chats/{chat_id}")
def chats_rename(chat_id: int, payload: ChatRenameRequest):
    init_db()
    item = rename_chat(chat_id, payload.title)
    if not item:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return item

@router.delete("/chats/{chat_id}")
def chats_delete(chat_id: int):
    init_db()
    delete_chat(chat_id)
    return {"status": "ok"}

@router.get("/chats/{chat_id}/messages")
def chats_messages(chat_id: int):
    init_db()
    return {"items": get_messages(chat_id)}

@router.post("/messages")
def messages_add(payload: ChatMessageRequest):
    init_db()
    chat_id = payload.chat_id
    if not chat_id:
        created = create_chat("Новый чат")
        chat_id = int(created["id"])
    message = add_message(chat_id, payload.role, payload.content)
    return {"status": "ok", "chat_id": chat_id, "message": message}
