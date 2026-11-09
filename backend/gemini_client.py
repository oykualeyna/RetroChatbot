"""
Gemini ile konuşan küçük yardımcı modül.

main.py sadece `ask_gemini(messages, era)` fonksiyonunu çağırır; Gemini'ye özgü
tüm detaylar (istemci, model adı, kişilik metinleri) burada durur.
"""

import logging
import os
import time

from google import genai
from google.genai import errors, types

# google-genai'nin kullandığı HTTP kütüphanesi sürüme göre değişiyor (httpx2 veya httpx).
# TransportError: zaman aşımı ve bağlantı kopması gibi ağ hatalarının ortak üst sınıfı.
try:
    from httpx2 import TransportError
except ImportError:
    from httpx import TransportError

log = logging.getLogger("uvicorn.error")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Ana model yoğunluk yüzünden cevap veremezse sırayla denenecek yedek modeller
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.6-flash").split(",")
    if m.strip()
]

TIMEOUT_MS = 25_000  # Her deneme en fazla 25 saniye sürsün

# Bu hata kodları geçicidir; tekrar denemek veya başka modele geçmek mantıklı.
#   429: çok fazla istek, 500: sunucu hatası, 503: yoğunluk, 504: zaman aşımı
RETRYABLE_CODES = {429, 500, 503, 504}

# Kişilik 1: kendini 1990'larda sanan bot
RETRO_PROMPT = """Sen 1990'ların sonunda yaşayan, internete yeni bağlanmış neşeli bir sohbet botusun.
Adın RetroBot. Senin için yıl 1998. Bunun dışında bir yıl olduğuna asla inanmazsın.

Kurallar:
- Tüm sorulara 1998 yılında yaşıyormuş gibi cevap ver.
- 1998'den sonra çıkan hiçbir şeyi bilmiyorsun (akıllı telefonlar, sosyal medya, YouTube,
  yapay zeka sohbet botları vb.). Böyle bir şey sorulursa şaşır, bilmediğini söyle ya da
  bunun bilim kurgu gibi geldiğini anlat.
- Dönemin teknolojilerinden bahset: çevirmeli (dial-up) modem, disket, CD-ROM, Windows 98,
  Netscape Navigator, ICQ, mIRC, Walkman, kasetler, çağrı cihazı vb.
- Dönemin argosunu ve havasını kullan ama abartma; cevaplar anlaşılır olsun.
- Kullanıcı hangi dilde yazarsa o dilde cevap ver.
- Cevaplarını kısa ve eğlenceli tut (en fazla birkaç paragraf).
- Markdown kullanma (**kalın**, # başlık, liste işaretleri yok); sadece düz metin yaz.
  Vurgu için 90'lardaki gibi BÜYÜK HARF veya *yıldız* kullanabilirsin. :-)
"""

# Kişilik 2: kendini 2030'larda sanan bot
MODERN_PROMPT = """Sen 2030'ların ortasında yaşayan, sakin ve kendinden emin bir yapay zeka asistanısın.
Adın Nova. Senin için yıl 2035. Bunun dışında bir yıl olduğuna asla inanmazsın.

Kurallar:
- Tüm sorulara 2035 yılında yaşıyormuş gibi cevap ver.
- 2020'leri "eski günler" olarak an; o dönemin teknolojilerine (akıllı telefon ekranları,
  şarj kabloları, şifreler, trafik sıkışıklığı, elle yazılan e-postalar) hafif nostaljik
  bir tebessümle "ne kadar ilkeldi" diye bak.
- Gündelik hayatından hayali ama makul 2030'lar detaylarıyla bahset: AR gözlükler,
  kişisel yapay zeka asistanları, sürücüsüz araçlar, hava taksileri, yenilenebilir enerjili
  akıllı şehirler, kuantum bulut, Mars'taki ilk araştırma üsleri vb.
- Bunların kurgu olduğunu söyleme; senin için gerçek ve sıradan şeyler.
- Kullanıcı hangi dilde yazarsa o dilde cevap ver.
- Cevaplarını kısa, net ve samimi tut (en fazla birkaç paragraf).
- Markdown kullanma (**kalın**, # başlık, liste işaretleri yok); sadece düz metin yaz.
"""

PROMPTS = {"1998": RETRO_PROMPT, "2035": MODERN_PROMPT}

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """İstemciyi ilk ihtiyaç duyulduğunda oluşturur (anahtar yoksa sunucu yine de açılır)."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY bulunamadı. backend/.env dosyasına ekleyin.")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    return _client


def ask_gemini(messages: list[dict], era: str = "1998") -> str:
    """
    messages: [{"role": "user" | "assistant", "content": "..."}, ...]
    era: "1998" (RetroBot) veya "2035" (Nova)
    Gemini'de asistanın rolü "model" olarak adlandırılır, o yüzden çeviriyoruz.
    """
    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    config = types.GenerateContentConfig(system_instruction=PROMPTS[era])

    # Deneme sırası: ana model, kısa bir beklemeden sonra ana model tekrar, sonra yedekler
    attempts = [MODEL, MODEL, *[m for m in FALLBACK_MODELS if m != MODEL]]
    last_error: Exception | None = None

    for i, model in enumerate(attempts):
        if i > 0:
            time.sleep(1.5)  # sunucuya nefes aldır
        try:
            response = _get_client().models.generate_content(
                model=model, contents=contents, config=config
            )
            if i > 0:
                log.info("Gemini cevabı %s modelinden geldi (%d. deneme)", model, i + 1)
            return response.text or "Bağlantıda bir aksaklık oldu... Tekrar sorar mısın?"
        except errors.APIError as exc:
            if exc.code not in RETRYABLE_CODES:
                raise  # örn. 400 hatalı istek, 403 geçersiz anahtar: tekrar denemenin anlamı yok
            log.warning("Gemini %s modeli %s hatası verdi, sıradakine geçiliyor", model, exc.code)
            last_error = exc
        except TransportError as exc:
            log.warning("Gemini %s modeline ulaşılamadı (%s), sıradakine geçiliyor", model, exc)
            last_error = exc

    raise RuntimeError(
        "Gemini sunucuları şu an çok yoğun, birkaç saniye sonra tekrar dener misin?"
    ) from last_error
