import json
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "phi3.5")

app = FastAPI()


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"|"assistant", "content": "..."}]


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(stream_chat(req.messages), media_type="text/plain")


async def stream_chat(messages: list[dict]):
    """
    Streams tokens from Ollama's /api/chat endpoint as plain text chunks.

    If you're using Triton, a homemade FastAPI/vLLM server, etc. instead of
    Ollama, replace the body of this function with a call to your server's
    API and yield text chunks the same way.
    """
    payload = {"model": MODEL_NAME, "messages": messages, "stream": True}
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{OLLAMA_URL}/api/chat", json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield f"[Error {resp.status_code} from inference server: {body.decode(errors='ignore')}]"
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
                        yield chunk
                    if data.get("done"):
                        break
    except httpx.ConnectError:
        yield (
            f"[Could not reach inference server at {OLLAMA_URL}. "
            "Is Ollama (or your server) running?]"
        )


PAGE = os.path.join(os.path.dirname(__file__), "index.html")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(PAGE, "r") as f:
        content = f.read()
    return content.replace("__MODEL_NAME__", MODEL_NAME)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8088)