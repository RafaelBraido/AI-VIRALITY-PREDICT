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


count_words = text_mod.count_words


BAND = (0.42, 0.90)  # faixa vertical lida pelo OCR (fração da altura)


def _lines(eng, small, min_conf):
    res, _ = eng(small)
    H, W = small.shape[:2]
    out = []
    for box, txt, conf in (res or []):
        txt = txt.strip()
        if float(conf) < min_conf or len(txt) < 2:
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        out.append((txt, BAND[0] + (BAND[1] - BAND[0]) * float(np.mean(ys)) / H, min(xs) / W, max(xs) / W))
    return out


def _worker_init():
    os.environ["OMP_NUM_THREADS"] = "1"  # N processos x 1 thread rende mais que 1 processo x N threads


def _worker_read(args):
    img, min_conf = args
    eng = _engine()
    return _lines(eng, img, min_conf) if eng is not None else []


def ocr_start(path: str, duration: float, rate: float = 1.5, max_samples: int = 90, min_conf: float = 0.6):
    """Decodifica os quadros com legenda e DISPARA a leitura em processos (não espera). Termine com ocr_finish."""
    if _engine() is None:
        return None
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = duration or 60.0
    rate = min(rate, max_samples / max(total, 1.0))
    step = max(1, int(round(fps / rate)))
    plan: list[tuple[float, int | None, int | None]] = []  # (t, idx do job, idx do job a reaproveitar)
    jobs, prev_gray, prev_job, idx = [], None, None, 0
    while True:
        if not cap.grab():
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                t = idx / fps
                H0 = frame.shape[0]
                # legendas ficam na metade de baixo: lê só essa faixa e devolve y no quadro todo
                small = F.resize_width(frame[int(H0 * BAND[0]):int(H0 * BAND[1])], 440)
                g = cv2.cvtColor(cv2.resize(small, (48, 40)), cv2.COLOR_BGR2GRAY)
                if prev_gray is not None and float(np.mean(cv2.absdiff(g, prev_gray))) < 1.5:
                    plan.append((t, prev_job))  # quadro praticamente igual: reaproveita a leitura anterior
                elif not F.text_regions(small):
                    plan.append((t, None))
                    prev_job = None
                else:
                    jobs.append((small, min_conf))
                    prev_job = len(jobs) - 1
                    plan.append((t, prev_job))
                prev_gray = g
        idx += 1
    cap.release()
    workers = min(max(1, (os.cpu_count() or 1) - 1), 4, max(1, len(jobs) // 6))
    ex, futs = None, None
    if workers > 1:
        try:
            import concurrent.futures as cf
            ex = cf.ProcessPoolExecutor(max_workers=workers, initializer=_worker_init)
            futs = [ex.submit(_worker_read, j) for j in jobs]
        except Exception:
            ex, futs = None, None
    return {"plan": plan, "jobs": jobs, "ex": ex, "futs": futs, "dt": step / fps}


def ocr_finish(h):
    if h is None:
        return [], 0.5
    results = None
    if h["futs"] is not None:
        try:
            results = [f.result() for f in h["futs"]]
        except Exception:
            results = None
        h["ex"].shutdown(wait=False)
    if results is None or len(results) != len(h["jobs"]):
        eng = _engine()
        results = [_lines(eng, img, mc) for img, mc in h["jobs"]]
    return [(t, results[j] if j is not None else []) for t, j in h["plan"]], h["dt"]


def ocr_collect(path: str, duration: float):
    return ocr_finish(ocr_start(path, duration))


def _is_name_tag(text: str) -> bool:
    """Etiqueta de quem fala (ex.: 'Zeca', 'Tonhão'): uma palavra curta com maiúscula só na inicial."""
    return (len(text.split()) == 1 and 2 <= len(text) <= 12 and text[0].isupper() and any(c.islower() for c in text)
            and text.isalpha())


def ocr_assemble(samples, dt):
    """Separa o texto lido em: legenda do DIÁLOGO (faixa vertical onde mais linhas se renovam), gráficos da cena
    (banners, títulos, rótulos), nomes de quem fala e overlays fixos (marca d'água).

    Retorna (cues, extra) com extra = {"fixed", "speakers", "graphics": [(t, texto)]}.
    """
    if not samples:
        return None, {}
    T = len(samples)
    tracks: list[dict] = []
    for t, lines in samples:
        for txt, y, x0, x1 in lines:
            k = _norm(txt)
            if not k:
                continue
            best = None
            for tr in tracks:
                if (t - tr["times"][-1] <= 2.2 * dt and abs(tr["y"] - y) < 0.05
                        and difflib.SequenceMatcher(None, tr["k"], k).ratio() >= 0.7):
                    best = tr
                    break
            if best is None:
                tracks.append({"k": k, "text": txt, "y": y, "times": [t]})
            else:
                best["times"].append(t)
                if len(txt) > len(best["text"]):
                    best["text"], best["k"] = txt, k
    speakers = sorted({tr["text"] for tr in tracks if _is_name_tag(tr["text"]) and len(tr["times"]) >= 3})
    rest = [tr for tr in tracks if tr["text"] not in speakers and (len(tr["times"]) >= 2 or len(tr["text"]) >= 5)]
    fixed = [tr for tr in rest if len(tr["times"]) >= 0.5 * T]
    rest = [tr for tr in rest if tr not in fixed]
    if not rest:
        return None, {"fixed": [tr["text"] for tr in sorted(fixed, key=lambda t: t["y"])], "speakers": speakers, "graphics": []}
    # faixa da legenda: onde mais linhas distintas passam (legenda renova o tempo todo)
    buckets: dict[int, int] = {}
    for tr in rest:
        buckets[int(tr["y"] / 0.06)] = buckets.get(int(tr["y"] / 0.06), 0) + len(tr["times"])
    cy = (max(buckets, key=buckets.get) + 0.5) * 0.06
    cap_tracks = [tr for tr in rest if abs(tr["y"] - cy) <= 0.06]
    graphics = sorted([(tr["times"][0], tr["text"]) for tr in rest if tr not in cap_tracks])
    cap_tracks.sort(key=lambda tr: tr["times"][0])
    cues: list[dict] = []
    for tr in cap_tracks:
        a0, b0 = tr["times"][0], tr["times"][-1] + dt
        for c in cues:
            ov = min(b0, c["b"]) - max(a0, c["a"])
            if ov >= 0.6 * min(b0 - a0, c["b"] - c["a"]):
                if not any(difflib.SequenceMatcher(None, _norm(tr["text"]), _norm(t_)).ratio() >= 0.7 for _, t_ in c["parts"]):
                    c["parts"].append((tr["y"], tr["text"]))
                c["a"], c["b"] = min(c["a"], a0), max(c["b"], b0)
                break
        else:
            cues.append({"a": a0, "b": b0, "parts": [(tr["y"], tr["text"])]})
    out = [(c["a"], c["b"], " ".join(t for _, t in sorted(c["parts"]))) for c in sorted(cues, key=lambda c: c["a"])]
    extra = {"fixed": [tr["text"] for tr in sorted(fixed, key=lambda t: t["y"])], "speakers": speakers,
             "graphics": [(round(t, 1), x) for t, x in graphics]}
    return (out or None), extra


def ocr_read(path: str, duration: float):
    samples, dt = ocr_collect(path, duration)
    return ocr_assemble(samples, dt)


def prepare(path: str, duration: float, transcript=None, ocr: bool = True) -> dict:
    """Resolve o que é rápido (texto enviado, .srt, legenda embutida); se não achar, já DISPARA o OCR em segundo plano."""
    if transcript:
        return {"cues": text_mod.parse(transcript), "source": "texto enviado por você", "extra": {}, "ocr": None}
    c = sidecar(path)
    if c:
        return {"cues": c, "source": "arquivo .srt/.vtt ao lado do vídeo", "extra": {}, "ocr": None}
    c = embedded(path)
    if c:
        return {"cues": c, "source": "legenda embutida no arquivo", "extra": {}, "ocr": None}
    return {"cues": None, "source": None, "extra": {}, "ocr": ocr_start(path, duration) if ocr else None}


def resolve(pre: dict, path: str, do_transcribe: bool = False):
    """Termina o OCR (se houver) e devolve (cues, fonte, extra); extra traz título/gráficos e nomes de quem fala."""
    if pre["cues"]:
        return pre["cues"], pre["source"], pre["extra"]
    extra = {}
    if pre["ocr"] is not None:
        c, extra = ocr_assemble(*ocr_finish(pre["ocr"]))
        if c and sum(count_words(t) for _, _, t in c) >= 3:
            return c, "texto lido na tela (OCR)", extra
    if do_transcribe:
        c = text_mod.transcribe(path)
        if c:
            return c, "Whisper", extra
    return None, None, extra


def find(path: str, duration: float, transcript=None, do_transcribe: bool = False, ocr: bool = True):
    return resolve(prepare(path, duration, transcript, ocr), path, do_transcribe)
