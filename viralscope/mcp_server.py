"""Servidor MCP (stdio, sem dependências) para o Claude chamar o viralscope direto.

Conectar:  claude mcp add viralscope -- viralscope-mcp
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile

from . import __version__
from .cli import main as cli_main

TOOLS = {
    "analyze_video": {
        "description": "Analisa um vídeo curto (MP4/MOV/WEBM) ou áudio (MP3/WAV/M4A) pelo caminho do arquivo. Lê sozinho legendas, "
                       "texto na tela e áudio. Devolve veredito (gancho, roteiro, imagem, áudio, retenção), cenas e correções.",
        "schema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "caminho do arquivo de vídeo ou áudio"},
            "platform": {"type": "string", "enum": ["shorts", "tiktok", "reels"], "default": "shorts"},
            "transcript": {"type": "string", "description": "opcional: caminho de .srt/.vtt/.txt ou o próprio roteiro"}},
            "required": ["path"]},
    },
    "analyze_script": {
        "description": "Analisa um roteiro em texto: gancho, clareza, especificidade, promessa x entrega, muletas, CTA.",
        "schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    "rank_hooks": {
        "description": "Ranqueia vários ganchos (frases de abertura) do melhor para o pior.",
        "schema": {"type": "object", "properties": {"hooks": {"type": "array", "items": {"type": "string"}}}, "required": ["hooks"]},
    },
    "analyze_image": {
        "description": "Analisa uma thumbnail/capa/primeiro quadro (arquivo de imagem).",
        "schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    "learn": {
        "description": "Registra a métrica real de um vídeo (retenção %, views em 7 dias...) para o modelo do canal aprender.",
        "schema": {"type": "object", "properties": {"path": {"type": "string"}, "target": {"type": "number"}}, "required": ["path", "target"]},
    },
}


def _run(argv: list[str]) -> str:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli_main(argv)
        except SystemExit as e:
            code = 1
            err.write(str(e))
    text = out.getvalue().strip()
    if code != 0 or not text:
        raise RuntimeError((err.getvalue().strip() or text) or "falha sem mensagem")
    return text


def call(name: str, a: dict) -> str:
    if name == "analyze_video":
        argv = ["analyze", a["path"], "--platform", a.get("platform", "shorts")]
        if a.get("transcript"):
            argv += ["--transcript", a["transcript"]]
        return _run(argv)
    if name == "analyze_script":
        return _run(["script", a["text"]])
    if name == "rank_hooks":
        return _run(["hooks", "|".join(h.replace("|", " ") for h in a["hooks"])])
    if name == "analyze_image":
        return _run(["image", a["path"]])
    if name == "learn":
        return _run(["learn", a["path"], "--target", str(a["target"])])
    raise KeyError(name)


def handle(msg: dict) -> dict | None:
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:  # notificação
        return None
    ok = lambda result: {"jsonrpc": "2.0", "id": mid, "result": result}
    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                   "serverInfo": {"name": "viralscope", "version": __version__}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{"name": n, "description": t["description"], "inputSchema": t["schema"]} for n, t in TOOLS.items()]})
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"ferramenta desconhecida: {name}"}}
        try:
            return ok({"content": [{"type": "text", "text": call(name, params.get("arguments") or {})}]})
        except Exception as e:  # erro de uso vira resultado de erro, não derruba o servidor
            return ok({"isError": True, "content": [{"type": "text", "text": f"Erro: {e}"}]})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"método não suportado: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
