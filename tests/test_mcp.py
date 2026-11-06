import json
import subprocess
import sys

from conftest import needs_ffmpeg


def _talk(msgs):
    p = subprocess.run([sys.executable, "-m", "viralscope.mcp_server"], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                       capture_output=True, text=True, timeout=120)
    return [json.loads(l) for l in p.stdout.splitlines()]


def test_handshake_and_tool_list():
    out = _talk([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                 {"jsonrpc": "2.0", "method": "notifications/initialized"},
                 {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
    assert out[0]["result"]["serverInfo"]["name"] == "viralscope" and out[0]["result"]["protocolVersion"] == "2025-03-26"
    names = {t["name"] for t in out[1]["result"]["tools"]}
    assert names == {"analyze_video", "analyze_script", "rank_hooks", "analyze_image", "learn"}
    assert len(out) == 2  # a notificação não gera resposta


def test_script_and_hooks_tools():
    out = _talk([{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "rank_hooks", "arguments": {"hooks": ["Oi pessoal, hoje eu vou falar", "Você toma café errado há 8 anos?"]}}},
                 {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "analyze_script", "arguments": {"text": "Você sabia que isso custa R$ 500 por mês? Veja como evitar. Comenta aqui."}}}])
    assert "Você toma café" in out[0]["result"]["content"][0]["text"].splitlines()[0]
    assert "duração falada" in out[1]["result"]["content"][0]["text"]


def test_errors_do_not_crash_server():
    out = _talk([{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "analyze_video", "arguments": {"path": "/nao/existe.mp4"}}},
                 {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nada", "arguments": {}}},
                 {"jsonrpc": "2.0", "id": 3, "method": "ping"}])
    assert out[0]["result"]["isError"] is True
    assert out[1]["error"]["code"] == -32602 and out[2]["result"] == {}


@needs_ffmpeg
def test_analyze_video_tool(vids):
    out = _talk([{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "analyze_video", "arguments": {"path": vids["dyn"]}}}])
    assert out[0]["result"]["content"][0]["text"].startswith("VEREDITO")
