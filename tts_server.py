"""
로컬 OpenVoice v2 TTS 서버 (CPU 전용)
------------------------------------
- 서버 시작 시 MeloTTS 베이스 모델 + OpenVoice ToneColorConverter를 '한 번만' 로드합니다.
- 유저 목소리 파일(reference.wav)에서 톤컬러 임베딩(target_se)도 시작할 때 한 번만 추출합니다.
  (요청마다 다시 추출하면 매번 몇 초씩 더 걸리기 때문에 반드시 캐싱)
- main.py는 이 서버의 /tts 엔드포인트를 호출해서 음성을 받아옵니다.

사전 준비 (최초 1회):
    pip install openvoice-cli melo-tts fastapi uvicorn

    # OpenVoice 체크포인트 다운로드 (v2)
    # https://github.com/myshell-ai/OpenVoice 의 안내에 따라
    # checkpoints_v2/converter 폴더를 이 파일과 같은 경로에 둡니다.

    # 본인 목소리 파일 준비
    #   - 형식: wav, 16k~24k 샘플레이트 권장
    #   - 길이: 10~30초 정도의 깨끗한 육성 (잡음/배경음 최소화)
    #   - 파일명: reference.wav 로 이 파일과 같은 폴더에 위치
"""

import io
import os
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from melo.api import TTS as MeloTTS
from openvoice.api import ToneColorConverter
from openvoice import se_extractor

app = FastAPI()

DEVICE = "cpu"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONVERTER_CKPT_DIR = os.path.join(BASE_DIR, "checkpoints_v2", "converter")
REFERENCE_WAV = os.path.join(BASE_DIR, "reference.wav")
TARGET_SE_CACHE = os.path.join(BASE_DIR, "target_se.pth")

print("[초기화] MeloTTS 로딩 중... (한국어 모델)")
melo_model = MeloTTS(language="KR", device=DEVICE)
speaker_ids = melo_model.hps.data.spk2id
DEFAULT_SPEAKER_KEY = list(speaker_ids.keys())[0]
DEFAULT_SPEAKER_ID = speaker_ids[DEFAULT_SPEAKER_KEY]

print("[초기화] OpenVoice ToneColorConverter 로딩 중...")
tone_converter = ToneColorConverter(
    os.path.join(CONVERTER_CKPT_DIR, "config.json"),
    device=DEVICE,
)
tone_converter.load_ckpt(os.path.join(CONVERTER_CKPT_DIR, "checkpoint.pth"))

# 베이스 화자(MeloTTS 기본 목소리)의 톤컬러 임베딩 - 이것도 한 번만 계산
source_se, _ = se_extractor.get_se(
    REFERENCE_WAV,  # 임시로 같은 파일 넣어도 되지만, 아래에서 target_se만 실제로 사용
    tone_converter,
    vad=True,
)

print("[초기화] 유저 목소리 톤컬러 추출 중... (최초 1회, 몇 초 소요)")
if os.path.exists(TARGET_SE_CACHE):
    target_se = torch.load(TARGET_SE_CACHE)
    print("[초기화] 캐시된 target_se 로드 완료")
else:
    target_se, _ = se_extractor.get_se(
        REFERENCE_WAV,
        tone_converter,
        vad=True,
    )
    torch.save(target_se, TARGET_SE_CACHE)
    print("[초기화] target_se 추출 및 캐시 저장 완료")

print("[초기화] 완료! 서버 준비됨.")


class TTSRequest(BaseModel):
    text: str


@app.post("/tts")
async def synthesize(request: TTSRequest):
    text = request.text
    tmp_base_wav = os.path.join(BASE_DIR, "_tmp_base.wav")
    tmp_out_wav = os.path.join(BASE_DIR, "_tmp_out.wav")

    try:
        # 1. MeloTTS로 기본 음성 생성 (빠름, non-autoregressive)
        melo_model.tts_to_file(
            text,
            DEFAULT_SPEAKER_ID,
            tmp_base_wav,
            speed=1.0,
        )

        # 2. OpenVoice로 톤컬러를 유저 목소리로 변환
        tone_converter.convert(
            audio_src_path=tmp_base_wav,
            src_se=source_se,
            tgt_se=target_se,
            output_path=tmp_out_wav,
        )

        with open(tmp_out_wav, "rb") as f:
            audio_bytes = f.read()

        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")

    except Exception as e:
        print(f"[오류] TTS 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS 에러: {str(e)}")
    finally:
        for f in (tmp_base_wav, tmp_out_wav):
            if os.path.exists(f):
                os.remove(f)


if __name__ == "__main__":
    import uvicorn
    # main.py(8000)와 겹치지 않게 8001 포트 사용
    uvicorn.run(app, host="0.0.0.0", port=8001)
