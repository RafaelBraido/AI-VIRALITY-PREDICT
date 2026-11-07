"""O que falta para a nota 10: contas exatas sobre a nota (não chute) e filtro de qualidade de roteiro.

A nota geral é uma média ponderada de componentes (0..1). Logo, o ganho de levar um componente ao alvo é
peso * (alvo - atual) / soma_dos_pesos * 100 pontos. A soma dos ganhos até 100% é exatamente 100 - nota.
Isso mede qualidade do MATERIAL com sinais do arquivo; NÃO garante views.
"""
from __future__ import annotations

import re

from . import text as text_mod

AREA = {"hook": "gancho", "body": "retenção", "sustain": "retenção", "no_drift": "retenção", "image": "imagem",
        "format": "formato", "loop": "loop", "captions": "legendas", "audio_tech": "áudio", "script": "roteiro"}
_TIPS = {
    "hook": "troque a abertura por pergunta, número ou contraste, com movimento e som no 1º segundo",
    "body": "varie o meio: corte, zoom ou mudança de plano a cada 3–5 s",
    "sustain": "encurte as partes em que a energia cai",
    "no_drift": "elimine trechos parados sem fala nem som",
    "image": "melhore nitidez, luz e um sujeito dominante no quadro",
    "format": "ajuste duração e resolução ao formato da plataforma",
    "loop": "feche repetindo o 1º quadro ou som para convidar a rever",
    "captions": "adicione ou suba as legendas (muita gente assiste sem som)",
    "audio_tech": "normalize o áudio perto de -14 LUFS e evite estourar",
    "script": "enxugue o texto, dê um dado concreto e deixe a resposta explícita",
}
TARGET = 0.9


def _score(comps: dict, w: dict, target: float | None) -> float:
    tot = sum(w[k] for k in comps)
    return 100.0 * sum(w[k] * (max(comps[k], target) if target is not None else comps[k]) for k in comps) / tot


def video_gaps(res: dict) -> dict:
    """Ganho exato (em pontos) de cada componente até 100%, ordenado; nota se todos chegarem a 90% e a 100%."""
    comps = res["components"]
    w = res.get("weights") or {k: 1.0 for k in comps}
    w = {k: w.get(k, 1.0) for k in comps}
    tot = sum(w.values())
    acts: dict[str, list[str]] = {}
    for v in res.get("verdicts", []):
        acts[v["area"]] = v.get("actions", [])
    rows = []
    for k, x in comps.items():
        gain = w[k] * (1 - x) / tot * 100
        if gain < 0.4:
            continue
        a = acts.get(AREA[k]) or []
        rows.append({"key": k, "area": AREA[k], "now": round(x, 3), "gain": round(gain, 1),
                     "gain_90": round(w[k] * max(0.0, TARGET - x) / tot * 100, 1),
                     "action": (a[0] if a else _TIPS[k])})
    merged: dict[str, dict] = {}
    for r in rows:  # componentes da mesma área (ex.: retenção) viram uma linha só
        m = merged.setdefault(r["area"], {**r, "now": 0.0, "gain": 0.0, "gain_90": 0.0, "_n": 0})
        m["gain"] += r["gain"]; m["gain_90"] += r["gain_90"]; m["now"] += r["now"]; m["_n"] += 1
        if r["gain"] > m.get("_best", 0):
            m["_best"], m["action"] = r["gain"], r["action"]
    rows = []
    for m in merged.values():
        n = m.pop("_n"); m.pop("_best", None)
        m["now"] = round(m["now"] / n, 3); m["gain"] = round(m["gain"], 1); m["gain_90"] = round(m["gain_90"], 1)
        rows.append(m)
    rows.sort(key=lambda r: -r["gain"])
    return {"score": round(res["overall"], 1), "score_10": round(res["overall"] / 10, 1), "rows": rows,
            "at_90": round(_score(comps, w, TARGET), 1), "at_100": round(_score(comps, w, 1.0), 1)}


def lines_gaps(g: dict, n: int = 3) -> list[str]:
    out = [f"PARA CHEGAR A 10 (hoje {g['score_10']:.1f}/10; cada item mostra quanto sobe a nota):"]
    for r in g["rows"][:n]:
        a = r["action"].split("Como:")[-1].strip()
        a = a if len(a) <= 130 else a[:130].rsplit(" ", 1)[0] + "…"
        out.append(f"  - {r['area']} {r['now'] * 100:.0f}% → 100%: +{r['gain']:.1f} pts. {a}")
    out.append(f"  Se todas as áreas chegarem a 90%: nota {g['at_90']:.0f}/100. 10/10 exige 100% em tudo, o que é raro. "
               "A nota mede a qualidade do material, não garante views.")
    return out


# ----------------------------------------------------------------------- filtro de qualidade do roteiro
def script_filter(raw: str, duration: float | None = None) -> dict:
    """10 critérios objetivos. Nota = critérios cumpridos (0–10). Cada falha traz o quê / por quê / como."""
    clean = " ".join(raw.split())
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    words = clean.split()
    est = duration or len(words) / 2.7
    first = text_mod.score_hook_text(sents[0] if sents else "")
    head = text_mod.score_hook_text(" ".join(words[:27]))
    q = text_mod.script_quality(clean, duration) or {}
    probs = " | ".join(n["problem"] for n in q.get("notes", []) if isinstance(n, dict))
    m = q.get("metrics", {})
    nums = text_mod._numbers(" ".join(words[:27]))
    checks = [
        ("Gancho com mecanismo", bool(first["signals"]) and first["score"] >= 0.5,
         "a 1ª frase decide se a pessoa fica", "abra com pergunta, número, contraste ou resultado antes da explicação"),
        ("Número ou dado nos 10 s iniciais", bool(nums), "dado concreto dá credibilidade e prende",
         "coloque um número real da história logo na abertura (dias, litros, valor)"),
        ("Promessa específica + algo incompleto", head["score"] >= 0.5 and bool(set(head["signals"]) & text_mod._LOOP_MECH),
         "sem lacuna aberta ninguém espera a resposta", "prometa um resultado e deixe a explicação para depois"),
        ("Frases curtas (até ~20 palavras)", "mais de 22 palavras" not in probs,
         "frase longa é difícil de acompanhar ouvindo", "quebre em frases de até ~15 palavras"),
        ("Sem muletas", "muletas" not in probs, "'tipo', 'né' enchem sem informar", "corte as muletas no texto"),
        ("Resposta explícita na 2ª metade", m.get("fecha_promessa", True) or not m.get("abre_promessa", False),
         "pergunta sem resposta frustra e derruba a retenção",
         'diga a resposta com clareza ("ou seja…", "o resultado foi…"). Detecção por palavras-chave: se a resposta já está clara, ignore'),
        ("Exemplos concretos suficientes", "poucos números" not in probs,
         "afirmação genérica passa batida", 'troque afirmações por dados ("8 meses", "3 passos")'),
        ("Sem repetição", "repetidos" not in probs, "cada frase tem de avançar a história", "corte o trecho repetido"),
        ("Final com fecho ou pergunta", "termina sem fecho" not in probs,
         "o final decide comentário, compartilhamento e rever", "termine com conclusão, pergunta ou gancho do próximo"),
        ("Duração adequada (30–60 s falados)", 30 <= est <= 62 and "longo demais" not in probs,
         "curto demais não entrega, longo demais perde", "ajuste o texto para ~100–150 palavras"),
    ]
    rows = [{"criterio": c, "ok": ok, "por_que": why, "como": how} for c, ok, why, how in checks]
    score = sum(1 for r in rows if r["ok"])
    return {"score_10": score, "approved": score >= 9, "est_duration_s": round(est, 1), "criteria": rows}


def lines_filter(f: dict) -> list[str]:
    out = [f"FILTRO DE QUALIDADE: {f['score_10']}/10 — " + ("APROVADO" if f["approved"] else "REPROVADO (precisa de 9/10 para aprovar)")]
    for r in f["criteria"]:
        if r["ok"]:
            out.append(f"  [ok] {r['criterio']}")
        else:
            out.append(f"  [falta] {r['criterio']}. Por quê: {r['por_que']}. Como: {r['como']}.")
    out.append("  Para chegar a 10/10, cumpra todos os itens [falta]. Isso mede qualidade do roteiro, não garante views.")
    return out


def lines_filter_short(f: dict) -> list[str]:
    """Versão curta para o resumo do vídeo: nota e só o que falta."""
    falta = [r["criterio"] for r in f["criteria"] if not r["ok"]]
    out = [f"FILTRO DE QUALIDADE DO ROTEIRO: {f['score_10']}/10 — " + ("APROVADO" if f["approved"] else "REPROVADO (9/10 aprova)")]
    if falta:
        out.append("  Falta: " + "; ".join(falta) + ". Detalhe de cada um: `viralscope script` com o texto.")
    return out


def lines_verdict10(g: dict, f: dict | None) -> str:
    """Resposta direta à pergunta 'daria 10?'."""
    ok = g["score_10"] >= 9.95
    falta = [r["area"] for r in g["rows"][:3]]
    s = f"DARIA 10? {'Sim, está no topo.' if ok else 'Ainda não.'} Hoje {g['score_10']:.1f}/10"
    if not ok:
        s += f"; para 10 falta: {', '.join(falta)}"
    if f is not None and not f["approved"]:
        s += f"; o roteiro reprovou no filtro ({f['score_10']}/10)"
    return s + "."
