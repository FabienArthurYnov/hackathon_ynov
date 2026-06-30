import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "phi3.5")
HISTORY_FILE = Path(__file__).with_name("chat_history.json")

app = FastAPI()
conversation_history: list[dict] = []


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"|"assistant", "content": "..."}]


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_history(history: list[dict]) -> None:
    try:
        with HISTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError:
        pass


async def check_model_connection() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        return False


@app.get("/api/health")
async def health() -> dict:
    return {"ok": await check_model_connection()}


@app.get("/api/history")
async def get_history() -> list[dict]:
    return conversation_history


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(stream_chat(req.messages), media_type="text/plain")


async def stream_chat(messages: list[dict]):
    """
    Streams tokens from Ollama's /api/chat endpoint as plain text chunks.
    """
    payload = {"model": MODEL_NAME, "messages": messages, "stream": True}
    full_response = ""
    error_message = ""
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{OLLAMA_URL}/api/chat", json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    error_message = (
                        f"[Error {resp.status_code} from inference server: "
                        f"{body.decode(errors='ignore')}]"
                    )
                    yield error_message
                    return
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        full_response += chunk
                        yield chunk
                    if data.get("done"):
                        break
    except httpx.ConnectError:
        error_message = (
            f"[Could not reach inference server at {OLLAMA_URL}. "
            "Is Ollama (or your server) running?]"
        )
        yield error_message
    finally:
        global conversation_history
        assistant_content = full_response or error_message or ""
        if assistant_content:
            conversation_history = list(messages) + [
                {"role": "assistant", "content": assistant_content}
            ]
        else:
            conversation_history = list(messages)
        save_history(conversation_history)


conversation_history = load_history()

PAGE = os.path.join(os.path.dirname(__file__), "index.html")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(PAGE, "r", encoding="utf-8") as f:
        content = f.read()
    return content.replace("__MODEL_NAME__", MODEL_NAME)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8088)