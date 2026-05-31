"""Speech-to-Text API — local Whisper large-v3 via faster-whisper

Model auto-downloads to backend/models/whisper/ on first use (~3GB).
Chrome/Edge bypass this API (use browser's SpeechRecognition),
Safari/Firefox fall back here via MediaRecorder → POST audio blob.
"""

import io
import os
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

router = APIRouter(tags=["stt"])

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "whisper"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Set HuggingFace cache to our project directory
os.environ.setdefault("HF_HOME", str(MODEL_DIR.parent))

_model = None  # lazy load


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16",
            download_root=str(MODEL_DIR),
        )
    return _model


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """Convert uploaded audio (wav/mp3/webm/m4a) to text via local Whisper"""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    # Accept common audio formats
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".wav", ".mp3", ".webm", ".m4a", ".ogg", ".flac", ".opus"):
        raise HTTPException(400, f"Unsupported audio format: {suffix}")

    audio_bytes = await file.read()
    if len(audio_bytes) < 1024:
        raise HTTPException(400, "Audio file too small (< 1KB)")

    try:
        model = _get_model()
        segments, info = model.transcribe(
            io.BytesIO(audio_bytes),
            language="zh",
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return {"text": text, "language": info.language, "duration_s": info.duration}
    except Exception as e:
        raise HTTPException(500, f"Speech recognition failed: {str(e)}")
