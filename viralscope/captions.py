"""Descobre sozinho o TEXTO do vídeo, sem pedir nada ao usuário e sem Whisper.

Ordem: (1) legenda enviada por você; (2) arquivo .srt/.vtt com o mesmo nome do vídeo; (3) faixa de legenda
embutida no arquivo; (4) texto escrito na imagem (legendas queimadas, títulos, créditos) lido por OCR
(RapidOCR, instalado junto via pip); (5) Whisper, só se você já o tiver e pedir com --transcribe.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess

import cv2
import numpy as np

from . import frames as F
from . import text as text_mod

_OCR = None
_OCR_TRIED = False


def _engine():
    global _OCR, _OCR_TRIED
    if not _OCR_TRIED:
        _OCR_TRIED = True
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            _OCR = RapidOCR()
        except Exception:
            _OCR = None
    return _OCR


def ocr_available() -> bool:
    return _engine() is not None


def sidecar(path: str):
    stem = os.path.splitext(path)[0]
    for ext in (".srt", ".vtt"):
        p = stem + ext
        if os.path.isfile(p):
            cues = text_mod.parse(p)
            if cues and cues[0][0] is not None:
                return cues
    return None


def embedded(path: str):
    """Primeira faixa de legenda dentro do arquivo (mov_text, subrip, webvtt...)."""
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=index",
                         "-of", "json", path], capture_output=True, text=True)
    try:
        if not json.loads(pr.stdout).get("streams"):
            return None
    except json.JSONDecodeError:
        return None
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:s:0", "-f", "srt", "-"],
                       capture_output=True, text=True)
    if p.returncode != 0 or "-->" not in p.stdout:
        return None
    cues = text_mod.parse(p.stdout)
    return cues if cues and cues[0][0] is not None else None


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9à-ú]", "", t.lower())


def ocr_cues(path: str, duration: float, rate: float = 2.0, max_samples: int = 120, min_conf: float = 0.6):
    """Lê o texto da tela ~2x por segundo e junta quadros seguidos com o mesmo texto em um trecho."""
    eng = _engine()
    if eng is None:
        return None
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = duration or 60.0
    rate = min(rate, max_samples / max(total, 1.0))
    step = max(1, int(round(fps / rate)))
    samples: list[tuple[float, str]] = []
    prev_gray, prev_text, idx = None, "", 0
    while True:
        if not cap.grab():
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                t = idx / fps
                small = F.resize_width(frame, 540)
                g = cv2.cvtColor(cv2.resize(small, (48, 80)), cv2.COLOR_BGR2GRAY)
                if prev_gray is not None and float(np.mean(cv2.absdiff(g, prev_gray))) < 1.5:
                    txt = prev_text  # quadro praticamente igual: reaproveita a leitura anterior
                elif not F.text_regions(small):
                    txt = ""
                else:
                    res, _ = eng(small)
                    lines = sorted(((float(np.mean([p[1] for p in b[0]])), b[1]) for b in (res or []) if float(b[2]) >= min_conf),
                                   key=lambda x: x[0])
                    txt = " ".join(t_.strip() for _, t_ in lines if len(t_.strip()) >= 2)
                samples.append((t, txt))
                prev_gray, prev_text = g, txt
        idx += 1
    cap.release()
    dt = step / fps
    cues: list[list] = []
    for t, txt in samples:
        if not txt:
            continue
        k = _norm(txt)
        if cues and difflib.SequenceMatcher(None, cues[-1][3], k).ratio() >= 0.8 and t - cues[-1][1] <= 2 * dt + 0.01:
            cues[-1][1] = t + dt
            if len(txt) > len(cues[-1][2]):
                cues[-1][2] = txt
        else:
            cues.append([t, t + dt, txt, k])
    return [(a, b, t) for a, b, t, _ in cues] or None


def find(path: str, duration: float, transcript=None, do_transcribe: bool = False, ocr: bool = True):
    """Devolve (cues, fonte). Fonte: 'você enviou', 'arquivo .srt ao lado', 'legenda embutida', 'texto lido na tela (OCR)', 'Whisper'."""
    if transcript:
        return text_mod.parse(transcript), "texto enviado por você"
    c = sidecar(path)
    if c:
        return c, "arquivo .srt/.vtt ao lado do vídeo"
    c = embedded(path)
    if c:
        return c, "legenda embutida no arquivo"
    if ocr:
        c = ocr_cues(path, duration)
        if c and sum(len(t.split()) for _, _, t in c) >= 3:
            return c, "texto lido na tela (OCR)"
    if do_transcribe:
        c = text_mod.transcribe(path)
        if c:
            return c, "Whisper"
    return None, None
