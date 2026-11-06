"""Leitura rápida de quadros: o ffmpeg decodifica, reduz e (opcional) recorta; o Python só recebe pixels pequenos."""
from __future__ import annotations

import subprocess

import numpy as np


def frames(path: str, fps: float, width: int, src_w: int, src_h: int, crop: tuple[float, float] | None = None):
    """Gera quadros BGR (altura×largura×3) a `fps` quadros/s, com `width` px de largura.

    `crop=(a, b)` mantém só a faixa vertical de a até b da altura (frações). src_w/src_h já consideram rotação.
    """
    h_in = src_h * ((crop[1] - crop[0]) if crop else 1.0)
    out_w = width - width % 2
    out_h = max(2, int(round(h_in * out_w / src_w / 2)) * 2)
    vf = f"fps={fps}"
    if crop:
        vf += f",crop=iw:ih*{crop[1] - crop[0]:.4f}:0:ih*{crop[0]:.4f}"
    vf += f",scale={out_w}:{out_h}"
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-an", "-sn", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=out_w * out_h * 3 * 4)
    size = out_w * out_h * 3
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(out_h, out_w, 3).copy()
    finally:
        p.stdout.close()
        p.kill()
        p.wait()
