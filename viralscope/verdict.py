"""Veredito em linguagem de gente: "o gancho está bom, mas o roteiro precisa melhorar", com o porquê e o que fazer."""
from __future__ import annotations

import numpy as np

_PART_TXT = {
    "dyn": ("movimento e cortes nos 3 primeiros segundos", "abra com corte, movimento ou zoom já no segundo 0"),
    "frame": ("primeiro quadro (nitidez, luz, sujeito claro)", "escolha um primeiro quadro nítido, bem iluminado e com um sujeito dominante"),
    "audio": ("entrada do som", "comece com voz ou som no primeiro segundo; nada de silêncio inicial"),
    "text": ("frase de abertura", "reescreva a abertura com um mecanismo claro: pergunta, número, contrário ou promessa específica"),
}


def rate(x, hi=0.60, lo=0.40) -> str:
    return "bom" if x >= hi else ("ok" if x >= lo else "fraco")


_ART = {"gancho": ("O", "gancho", "m"), "roteiro": ("O", "roteiro", "m"), "imagem": ("A", "imagem", "f"),
        "áudio": ("O", "áudio", "m"), "retenção": ("O", "meio do vídeo (retenção)", "m")}


def _cap(label: str, serious: bool) -> str:
    """Problema grave na área impede o selo 'bom'."""
    return "ok" if (label == "bom" and serious) else label


def _headline(area: str, lab: str, why: str, has_actions: bool = False) -> str:
    art, noun, g = _ART[area]
    good = "bom" if g == "m" else "boa"
    word = {"bom": f"está {good}" + (", com ajustes" if has_actions else ""),
            "ok": "está razoável, dá para melhorar", "fraco": "precisa melhorar"}[lab]
    return f"{art} {noun} {word}" + (f" — {why}" if why else "")


def build(res: dict, v: dict, a: dict | None, hook_parts: dict, script: dict | None) -> list[dict]:
    out = []
    comps = res["components"]

    # ---- gancho
    def serious(area):
        return any(f["area"] == area and f["priority"] >= 0.85 for f in res["fixes"])

    hook = comps["hook"]
    lab = _cap(rate(hook), serious("gancho"))
    weak = sorted(hook_parts.items(), key=lambda kv: kv[1])
    strong = max(hook_parts.items(), key=lambda kv: kv[1])
    why = ""
    actions = []
    if lab == "bom":
        why = f"destaque: {_PART_TXT[strong[0]][0]}"
    if lab != "bom" or serious("gancho"):
        for k, x in weak[:2]:
            if x < 0.5:
                actions.append(_PART_TXT[k][1] + f" (hoje: {x * 100:.0f}%)")
        why = f"o que mais pesa contra: {_PART_TXT[weak[0][0]][0]}"
    ht = res.get("hook_text")
    if ht and ht["notes"]:
        actions += ht["notes"][:2]
    actions += [f["text"] for f in res["fixes"] if f["area"] == "gancho" and f["priority"] >= 0.85 and f["text"] not in actions][:2]
    out.append({"area": "gancho", "label": lab, "score": hook, "headline": _headline("gancho", lab, why, bool(actions)), "actions": actions[:4]})

    # ---- roteiro
    if script and script.get("score") is not None:
        sc = script["score"]
        lab = _cap(rate(sc, 0.65, 0.45), any(n["priority"] >= 0.8 for n in script["notes"]))
        acts = [f"{n['problem']}: {n['action']}" for n in script["notes"][:3]]
        proxy = " (estimado só pelo áudio; envie o texto para a análise real)" if script.get("proxy") else ""
        why = "" if lab == "bom" else (script["notes"][0]["problem"] if script["notes"] else "")
        out.append({"area": "roteiro", "label": lab, "score": sc, "proxy": bool(script.get("proxy")),
                    "headline": _headline("roteiro", lab, why, bool(acts)) + proxy, "actions": acts})
    else:
        out.append({"area": "roteiro", "label": "sem dados", "score": None, "proxy": False,
                    "headline": "Roteiro não avaliado: o vídeo não tem fala e não veio texto/legenda.", "actions": []})

    # ---- imagem
    img = comps["image"]
    lab = rate(img, 0.60, 0.45)
    acts = []
    sh, lm, fo = float(np.mean(v["sharpness_raw"])), float(np.mean(v["luma_mean"])), float(np.mean(v["focus"]))
    if sh < 60:
        acts.append("melhore a nitidez (foco, bitrate ou resolução)")
    if lm < 70:
        acts.append("clareie a imagem; está escura")
    elif lm > 190:
        acts.append("reduza a exposição; está estourada")
    if fo < 0.3:
        acts.append("deixe um sujeito dominar o quadro")
    out.append({"area": "imagem", "label": lab, "score": img,
                "headline": _headline("imagem", lab, "" if lab == "bom" else (acts[0] if acts else ""), bool(acts)), "actions": acts[:3]})

    # ---- áudio
    if a is not None:
        au = 0.5 * comps["audio_tech"] + 0.5 * float(res["regions"]["auditory"] or 0)
        lab = rate(au, 0.60, 0.40)
        acts = [f["text"] for f in res["fixes"] if f["area"] == "áudio"][:3]
        out.append({"area": "áudio", "label": lab, "score": au,
                    "headline": _headline("áudio", lab, "" if lab == "bom" or not acts else acts[0], bool(acts)), "actions": acts})
    else:
        out.append({"area": "áudio", "label": "fraco", "score": 0.0, "headline": "O vídeo não tem áudio.", "actions": ["adicione voz ou trilha"]})

    # ---- retenção (corpo do vídeo)
    ret = 0.6 * comps["sustain"] + 0.4 * comps["no_drift"]
    lab = rate(ret, 0.70, 0.45)
    acts = [f["text"] for f in res["fixes"] if f["area"] == "retenção"][:3]
    weak_scenes = [s for s in res.get("scenes", []) if s["label"] == "fraca"]
    if weak_scenes and not acts:
        s0 = weak_scenes[0]
        acts.append(f"a cena de {s0['t0']:.0f}–{s0['t1']:.0f} s é a mais fraca; encurte ou troque")
    out.append({"area": "retenção", "label": lab, "score": ret,
                "headline": _headline("retenção", lab, "" if lab == "bom" or not acts else acts[0], bool(acts)), "actions": acts})
    return out


def summary(verdicts: list[dict]) -> str:
    parts = []
    for x in verdicts:
        if x["label"] == "sem dados":
            continue
        word = {"bom": "bom", "ok": "razoável", "fraco": "precisa melhorar"}[x["label"]]
        parts.append(f"{x['area']}: {word}")
    return " · ".join(parts)


def scenes(v: dict, a: dict | None, engagement: np.ndarray, S: int) -> list[dict]:
    """Divide o vídeo em cenas (pelos cortes; sem cortes, blocos de 5 s) e avalia cada uma."""
    cuts = sorted(t for t in v["cut_times"] if 0.5 < t < S - 0.5)
    bounds = [0.0] + cuts + [float(S)]
    merged = [bounds[0]]
    for b in bounds[1:]:
        if b - merged[-1] < 1.0 and b != bounds[-1]:
            continue
        merged.append(b)
    if len(merged) - 1 < 3:
        merged = [float(x) for x in range(0, S, 5)] + [float(S)]
        if merged[-1] - merged[-2] < 1.0 and len(merged) > 2:
            merged.pop(-2)
    out = []
    for t0, t1 in zip(merged[:-1], merged[1:]):
        i0, i1 = int(t0), max(int(t0) + 1, int(np.ceil(t1)))
        sl = slice(i0, min(i1, S))
        eng = float(np.mean(engagement[sl]))
        mot = float(np.mean(v["motion"][sl]))
        txt = float(np.mean(v["text_ratio"][sl]) > 0.015)
        speech = float(np.mean(a["syll_rate"][sl] >= 2)) if a is not None else 0.0
        loud = float(np.mean(a["loud_db"][sl])) if a is not None else None
        lab = "forte" if eng >= 0.6 else ("ok" if eng >= 0.35 else "fraca")
        bits = []
        if mot < 0.03:
            bits.append("imagem quase parada")
        if a is not None and speech < 0.3:
            bits.append("sem fala")
        if a is not None and loud is not None and loud < -50:
            bits.append("silêncio")
        if not txt:
            bits.append("sem texto na tela")
        out.append({"t0": round(t0, 1), "t1": round(t1, 1), "engagement": round(eng, 3), "motion": round(mot, 3),
                    "speech": round(speech, 2), "text": bool(txt), "label": lab,
                    "note": ", ".join(bits) if lab != "forte" else ""})
    return out


def build_audio(res: dict, a: dict) -> list[dict]:
    """Veredito para arquivos só de áudio (gancho de voz, roteiro, áudio)."""
    comps = res["components"]
    out = []

    def serious(area):
        return any(f["area"] == area and f["priority"] >= 0.85 for f in res["fixes"])

    lab = _cap(rate(comps["hook"]), serious("gancho") or serious("áudio"))
    acts = [f["text"] for f in res["fixes"] if f["area"] == "gancho" or f["priority"] >= 0.85][:3]
    out.append({"area": "gancho", "label": lab, "score": comps["hook"],
                "headline": _headline("gancho", lab, "", bool(acts)), "actions": acts})
    script = res.get("script")
    if script and script.get("score") is not None:
        lab = _cap(rate(script["score"], 0.65, 0.45), any(n["priority"] >= 0.8 for n in script["notes"]))
        acts = [f"{n['problem']}: {n['action']}" for n in script["notes"][:3]]
        proxy = " (estimado só pelo áudio; envie o texto para a análise real)" if script.get("proxy") else ""
        out.append({"area": "roteiro", "label": lab, "score": script["score"], "proxy": bool(script.get("proxy")),
                    "headline": _headline("roteiro", lab, "", bool(acts)) + proxy, "actions": acts})
    else:
        out.append({"area": "roteiro", "label": "sem dados", "score": None,
                    "headline": "Roteiro não avaliado: sem fala detectada e sem texto.", "actions": []})
    au = comps["audio_tech"]
    lab = rate(au, 0.60, 0.40)
    acts = [f["text"] for f in res["fixes"] if f["area"] == "áudio"][:3]
    out.append({"area": "áudio", "label": lab, "score": au, "headline": _headline("áudio", lab, "", bool(acts)), "actions": acts})
    return out
