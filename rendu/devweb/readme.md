Simple single-page AI chat interface.

- FastAPI backend that proxies chat requests to a local Ollama server
  (default: http://localhost:11434) and streams the response back.
- One single HTML page served at "/" with a minimal chat UI (no build step,
  no frontend framework — just vanilla JS + fetch streaming).

Run:
    pip install fastapi uvicorn httpx
    python app.py

Then open http://localhost:8080 in your browser.

Configure:
    Set OLLAMA_URL and MODEL_NAME env vars if your model/server differ, e.g.:
        OLLAMA_URL=http://localhost:11434 MODEL_NAME=phi3.5 python app.py

If you're not using Ollama (e.g. Triton or your own server), only the
`/api/chat` endpoint below needs to change — see the comment in `stream_chat()`.