# hongjae 프로그램 실행 가이드 (OpenVoice v2 로컬 TTS)

## 폴더 구조 (최종)
```
hongjae/
├── main.py                          ← 챗봇 서버 (8000번 포트)
├── tts_server.py                    ← 음성 합성 서버 (8001번 포트)
├── reference.wav                    ← 본인 목소리 파일
├── target_se.pth                    ← (자동 생성됨) 목소리 톤컬러 캐시
├── .env                             ← GROQ_API_KEY 등 저장
└── checkpoints_v2/
    ├── converter/
    │   ├── config.json
    │   └── checkpoint.pth
    └── base_speakers/
        └── ses/
            └── kr.pth
```

---

## 매번 실행할 때 (설치 끝난 뒤부터는 이것만 하면 됨)

### 1. 터미널 2개를 엽니다

**터미널 1 — TTS 서버 (반드시 먼저 실행)**
```powershell
cd C:\Users\lunaj\Desktop\hongjae
conda activate melo_env
python tts_server.py
```
콘솔에 아래 두 줄이 뜨면 준비 완료:
```
[초기화] 완료! 서버 준비됨.
[디버그] source_se shape: ..., target_se shape: ...
```
(모델 로딩에 수십 초 걸릴 수 있음 — 이 창을 끄지 말고 그대로 둡니다)

**터미널 2 — 챗봇 서버**
```powershell
cd C:\Users\lunaj\Desktop\hongjae
conda activate melo_env
python main.py
```

### 2. 정상 동작 확인
터미널 2를 켜둔 채로, 프론트엔드(브라우저 등)에서 채팅을 보내거나
아래처럼 직접 테스트해도 됩니다:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/chat" `
  -Method Post `
  -Body '{"message": "안녕"}' `
  -ContentType "application/json" `
  -OutFile "reply.wav"
```
`reply.wav`가 생성되고 재생되면 정상입니다.

### 3. 종료
두 터미널 모두 `Ctrl + C`로 종료합니다. (TTS 서버부터 꺼도, 챗봇 서버부터 꺼도 상관없음)

---

## 처음부터 새로 설치해야 할 때 (환경이 깨졌을 때)

지금까지 겪었던 문제들을 반영한 순서입니다. 이 순서대로 하면 같은 에러들을 반복하지 않습니다.

```powershell
# 1. 환경 생성
conda create -n melo_env python=3.10 -y
conda activate melo_env

# 2. lzma DLL 문제 방지 (가장 먼저 설치)
conda install -c conda-forge xz -y

# 3. ffmpeg는 conda 말고 winget으로 (conda-forge ffmpeg는 gdk-pixbuf 충돌 有)
winget install ffmpeg
#    ↳ 설치 후 이 터미널 닫고 새로 열어서 conda activate melo_env 다시 실행

# 4. PyTorch (CPU 버전)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 5. MeloTTS
pip install melo-tts
python -m unidic download
pip install eunjeon      # 디스크 용량 부족하면 실패하니 여유 공간 확보 후 실행

# 6. OpenVoice 및 빠진 의존성들
pip install git+https://github.com/myshell-ai/OpenVoice.git
pip install wavmark
pip install whisper-timestamped
pip install faster-whisper

# 7. FastAPI 쪽
pip install fastapi uvicorn requests python-dotenv

# 8. 확인
python -c "import lzma; print('lzma ok')"
ffmpeg -version
python -c "from melo.api import TTS; print('melo ok')"
```

### 체크포인트 (한 번만 받으면 됨, 재설치해도 다시 안 받아도 됨)
```powershell
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='myshell-ai/OpenVoiceV2', local_dir='checkpoints_v2')"
```

### 목소리 파일
- `reference.wav`로 저장, `hongjae` 폴더 바로 밑에 위치
- 깨끗한 육성 10초~2분 정도, 잡음/다른 사람 목소리 최소화

---

## 자주 겪었던 에러 모음 (다시 나오면 여기서 찾기)

| 에러 메시지 | 원인 | 해결 |
|---|---|---|
| `No module named 'whisper_timestamped'` | 패키지 누락 | `pip install whisper-timestamped` |
| `No module named 'faster_whisper'` | 패키지 누락 | `pip install faster-whisper` |
| `FileNotFoundError: [WinError 2]` (load_audio 관련) | ffmpeg 없음 | `winget install ffmpeg` 후 터미널 재시작 |
| `ImportError: DLL load failed while importing _lzma` | liblzma.dll 없음 | `conda install -c conda-forge xz` |
| `DirectoryNotACondaEnvironmentError` | 환경 손상 | 환경 삭제 후 재생성 |
| `No space left on device` | 디스크 용량 부족 | `conda clean --all`, `pip cache purge`, 불필요 파일 정리 |
| `exceptions must derive from BaseException` | 실제 원인이 다른 에러 (위 표 항목들 확인) | traceback 전체를 보고 진짜 원인 찾기 |
| `could not broadcast input array from shape (0,) into shape (0,8)` | ① source_se를 잘못된 방식으로 추출했거나 ② `message=""`로 워터마크를 껐을 때 | source_se는 `base_speakers/ses/kr.pth`에서 로드, message는 기본값 사용 (비워두지 말 것) |
| `pip's dependency resolver ... incompatible` (numpy, gradio, faster-whisper 버전 경고) | myshell-openvoice의 requirements가 오래됨 | 실행이 되면 무시해도 됨 |

---

## 목소리 파일을 바꾸고 싶을 때
1. 새 `reference.wav`로 교체
2. `target_se.pth` 파일 삭제 (캐시라서 지워야 새로 추출함)
3. `tts_server.py` 재실행
