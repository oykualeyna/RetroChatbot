"""
Retro Chatbot - 1990'larda yaşadığını sanan bir chatbot (FastAPI backend).

Çalıştırmak için (proje kök klasöründen):
    uvicorn main:app --reload --app-dir backend
Sonra tarayıcıda: http://127.0.0.1:8000
"""

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

# backend/.env dosyasındaki GEMINI_API_KEY ve GEMINI_MODEL değerlerini yükle.
# gemini_client modeli import anında okuduğu için bu satır import'tan önce olmalı.
load_dotenv(BACKEND_DIR / ".env")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from gemini_client import ask_gemini  # noqa: E402

app = FastAPI(title="Retro Chatbot")


class Message(BaseModel):
    role: str  # "user" veya "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    # Hangi dönemin botu cevap versin: 1998 (RetroBot) veya 2035 (Nova)
    era: Literal["1998", "2035"] = "1998"


class ChatResponse(BaseModel):
    reply: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.messages:
        raise HTTPException(status_code=400, detail="Mesaj listesi boş olamaz.")

    # Sadece geçerli rolleri ve son 20 mesajı gönder (maliyeti sınırlamak için)
    history = [
        {"role": m.role, "content": m.content}
        for m in request.messages[-20:]
        if m.role in ("user", "assistant")
    ]

    try:
        reply = ask_gemini(history, request.era)
    except RuntimeError as exc:  # örn. API anahtarı eksik
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini hatası: {exc}") from exc

    return ChatResponse(reply=reply)


# Frontend dosyalarını (index.html, style.css, script.js) kök adresten sun.
# API route'larından SONRA eklenmeli, yoksa /api/chat isteklerini yutar.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
