from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import requests
import io
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-AI-Response-Text"]
)

# ⚠️ 여기에 발급받은 키들을 정확하게 넣어줘!
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "sk_a47fc2ea750fdb68fcc99583ada2820a9f8eebe33d8307f2")
VOICE_ID = os.getenv("VOICE_ID", "zSd701lJwatrGb2GJ9lm")

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_and_voice(request: ChatRequest):
    user_message = request.message

    # 1. Groq API 호출
    groq_url = "https://api.groq.com/openai/v1/chat/completions"
    groq_headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    groq_data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "너는 친구야. 반말로 2~3문장 이내로 짧게 카톡하듯 대답해줘."},
            {"role": "user", "content": "오늘 날씨 좋다"},
            {"role": "assistant", "content": "인정 ㅋㅋ 날씨 대박이네! 나가 놀고 싶다"},
            {"role": "user", "content": user_message}
        ]
    }

    try:
        groq_res = requests.post(groq_url, json=groq_data, headers=groq_headers)
        groq_res.raise_for_status()
        ai_text = groq_res.json()['choices'][0]['message']['content']
        print(f"[성공] Groq AI 답변 생성 완료: {ai_text}")
    except Exception as e:
        print(f"[오류] Groq API 단계에서 터짐: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Groq 에러: {str(e)}")

    # 2. ElevenLabs TTS API 호출 (안전한 기본 데이터 포맷 적용)
    eleven_url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    eleven_headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "accept": "audio/mpeg"
    }
    eleven_data = {
        "text": ai_text,
        "model_id": "eleven_multilingual_v2",  # 한국어 지원 공식 모델
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }

    try:
        eleven_res = requests.post(eleven_url, json=eleven_data, headers=eleven_headers)
        
        # 💡 만약 에러가 나면 ElevenLabs가 보낸 구체적인 거절 사유를 로그에 출력
        if not list(eleven_res.headers.keys()):
            pass
        if eleven_res.status_code != 200:
            print(f"[오류] ElevenLabs 응답 실패 코드: {eleven_res.status_code}")
            print(f"[오류] ElevenLabs 상세 메시지: {eleven_res.text}")
            raise HTTPException(status_code=eleven_res.status_code, detail=eleven_res.text)
            
        audio_bytes = eleven_res.content
        print("[성공] ElevenLabs 음성 합성 완료!")
    except Exception as e:
        print(f"[오류] ElevenLabs 단계에서 터짐: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ElevenLabs 에러: {str(e)}")

    # 3. 데이터 반환
    encoded_text = urllib.parse.quote(ai_text)
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={"X-AI-Response-Text": encoded_text}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)