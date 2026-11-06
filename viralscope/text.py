"""Transcrição (opcional), ritmo de fala e análise do gancho falado/escrito.

A pontuação do gancho é uma HEURÍSTICA de mecanismos (vocabulário), não um modelo treinado.
Os mecanismos vêm de taxonomias públicas de gancho (curiosidade, contrário, pergunta, número,
prova, dor, história, autoridade, urgência, 'você'); os pesos são priors editáveis.
"""
from __future__ import annotations

import os
import re

import numpy as np

# ---------------------------------------------------------------- transcrição
_TS = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)|(\d+):(\d+)[.,](\d+)")


def _to_sec(m: re.Match) -> float:
    g = m.groups()
    if g[0] is not None:
        return int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 10 ** len(g[3])
    return int(g[4]) * 60 + int(g[5]) + int(g[6]) / 10 ** len(g[6])


def parse(src: str) -> list[tuple[float | None, float | None, str]]:
    """Aceita caminho de .srt/.vtt/.txt ou o próprio texto. Retorna [(início, fim, texto)]."""
    raw = open(src, encoding="utf-8").read() if os.path.isfile(src) else src
    cues = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            if "-->" in line:
                a, b = line.split("-->")[:2]
                ma, mb = _TS.search(a), _TS.search(b)
                if ma and mb:
                    text = " ".join(lines[i + 1:])
                    text = re.sub(r"<[^>]+>", "", text)
                    cues.append((_to_sec(ma), _to_sec(mb), text))
                break
    if cues:
        return cues
    return [(None, None, " ".join(raw.split()))]


def transcribe(path: str):
    """faster-whisper ou openai-whisper, se instalados. Senão, None."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model = WhisperModel("small", compute_type="int8")
        segs, _ = model.transcribe(path)
        return [(s.start, s.end, s.text.strip()) for s in segs]
    except Exception:
        pass
    try:
        import whisper  # type: ignore
        res = whisper.load_model("small").transcribe(path)
        return [(s["start"], s["end"], s["text"].strip()) for s in res["segments"]]
    except Exception:
        return None


def words_per_second(cues, seconds: int) -> np.ndarray | None:
    if not cues or cues[0][0] is None:
        return None
    w = np.zeros(seconds)
    for a, b, text in cues:
        n = len(text.split())
        dur = max(b - a, 0.2)
        for s in range(int(a), min(int(np.ceil(b)), seconds)):
            lo, hi = max(a, s), min(b, s + 1)
            w[s] += n * max(0.0, hi - lo) / dur
    return w


def opening_text(cues, seconds_limit: float = 4.0) -> str:
    """Texto dito nos primeiros segundos (ou a primeira frase, se a transcrição não tem tempos)."""
    if not cues:
        return ""
    if cues[0][0] is None:
        return re.split(r"(?<=[.!?])\s+", cues[0][2])[0]
    return " ".join(t for a, b, t in cues if a < seconds_limit)


def first_word_time(cues) -> float | None:
    if not cues or cues[0][0] is None:
        return None
    return float(min(a for a, _, t in cues if t.strip()))


# ----------------------------------------------------------- gancho (heurística)
MECHANISMS = {
    "pergunta": (r"\?|^(por que|porque|como|qual|quais|quem|quando|onde|você sabia|vc sabia|sabe |"
                 r"what|why|how|who|when|did you|do you|are you|is it)\b", 0.14),
    "número/especificidade": (r"\d|\b(r\$|us\$|%|por cento|mil|milhão|milhões|million|thousand)\b", 0.14),
    "contrário/mito": (r"\b(não|nunca|pare de|para de|ninguém|mito|erro|errado|errada|jamais|mentira|"
                       r"stop|never|don't|dont|myth|mistake|wrong|nobody|lie|lying)\b", 0.14),
    "fala com 'você'": (r"\b(você|vc|voce|seu|sua|seus|suas|te|you|your|you're)\b", 0.10),
    "lacuna de curiosidade": (r"(segredo|ninguém te conta|ninguém fala|o que acontece|descobri|a verdade|"
                              r"por isso|o motivo|o real motivo|escondid|secret|nobody tells|what happens|"
                              r"the truth|here's why|here is why|hidden|what they don't)", 0.18),
    "dor/aposta": (r"\b(perder|perdendo|perdi|problema|cansad[oa]|medo|culpa|falha|falhar|quebrar|quebrou|"
                   r"arruinar|prejuízo|lose|losing|lost|problem|tired|afraid|fail|failing|ruin|broke)\b", 0.08),
    "prova/resultado": (r"\b(testei|provei|resultado|em \d+|consegui|ganhei|fiz|funcionou|prova|"
                        r"i tested|i tried|proof|result|worked|made \$)\b", 0.10),
    "história/confissão": (r"\b(eu (era|fui|fiz|perdi|achava|quase)|aconteceu|confesso|minha vez|"
                           r"i was|i used to|i almost|confession|happened)\b", 0.08),
    "autoridade": (r"\b(anos de|especialista|cientistas?|estudo|pesquisa|engenheir[oa]|médic[oa]|"
                   r"years of|expert|scientists?|study|research|engineer|doctor)\b", 0.06),
    "urgência/limite": (r"\b(agora|antes que|última chance|só hoje|em \d+ segundos|rápido|"
                        r"right now|before it|last chance|only today|in \d+ seconds|quickly)\b", 0.06),
}
_GENERIC = (r"^(oi|olá|ola|fala galera|fala pessoal|e aí|e ai|beleza|bom dia|boa tarde|boa noite|hoje eu vou|hoje vou|"
            r"neste vídeo|nesse vídeo|nesse short|bem-vindo|salve|hey guys|hi |hello|what's up|in this video|today i)")
_CTA_EARLY = r"\b(se inscreva|inscreva-se|deixa o like|curta|siga|segue|follow|subscribe|like and)\b"
_FILLER = r"^(então|tipo|é |né|hum|ahn|bom,|bem,|well,|so |um |uh)"


def score_hook_text(text: str) -> dict:
    t = text.strip().lower()
    if not t:
        return {"score": 0.0, "signals": [], "words": 0, "notes": ["Sem texto de abertura."]}
    words = len(t.split())
    hits = [k for k, (rx, _) in MECHANISMS.items() if re.search(rx, t)]
    weights = sorted((MECHANISMS[k][1] for k in hits), reverse=True)
    mech = sum(w * (0.75 ** i) for i, w in enumerate(weights))  # retorno decrescente
    score = 0.12 + mech
    notes = []
    if words <= 14:
        score += 0.14
    elif words <= 22:
        score += 0.06
    else:
        notes.append(f"Abertura longa ({words} palavras); enxugue para ~14 ou menos.")
    if re.search(_GENERIC, t):
        score -= 0.30
        notes.append("Abertura genérica (saudação/'hoje eu vou'); comece direto no conflito ou na promessa.")
    if re.search(_FILLER, t):
        score -= 0.08
        notes.append("Começa com muleta ('então', 'tipo', 'bom'); corte a primeira palavra.")
    if re.search(_CTA_EARLY, t):
        score -= 0.20
        notes.append("Pedido de inscrição/like logo na abertura; deixe para o fim.")
    if not hits:
        notes.append("Nenhum mecanismo de gancho detectado (pergunta, número, contrário, 'você', curiosidade, dor, prova).")
    return {"score": float(min(1.0, max(0.0, score))), "signals": hits, "words": words, "notes": notes}


def rank_hooks(hooks: list[str]) -> list[dict]:
    out = []
    for h in hooks:
        r = score_hook_text(h)
        r["hook"] = h
        out.append(r)
    return sorted(out, key=lambda r: -r["score"])


# ------------------------------------------------------------------ roteiro inteiro
_CTA_END = r"\b(se inscreva|inscreva-se|segue|siga|comenta|comente|curta|link|follow|subscribe|comment)\b"
_FILLER_WORDS = ("tipo", "né", "então", "assim", "basicamente", "like", "basically", "actually", "literally")


def analyze_script(text: str, wps_target: float = 2.7) -> dict:
    """Análise de roteiro (sem vídeo): gancho, ritmo estimado, frases longas, muletas, CTA."""
    clean = " ".join(text.split())
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    words = clean.split()
    lens = [len(s.split()) for s in sents]
    first10 = " ".join(words[: int(10 * wps_target)])
    hook = score_hook_text(sents[0] if sents else "")
    hook10 = score_hook_text(first10)
    low = clean.lower()
    filler = sum(low.count(f" {w} ") for w in _FILLER_WORDS)
    notes = list(hook["notes"])
    if lens and max(lens) > 24:
        notes.append(f"Há frase de {max(lens)} palavras; frases longas pioram a clareza falada (alvo ≤ 20).")
    if filler / max(1, len(words)) > 0.03:
        notes.append("Muitas muletas ('tipo', 'né', 'então'...); enxugue.")
    has_cta_end = bool(re.search(_CTA_END, " ".join(sents[-2:]).lower())) if sents else False
    return {
        "words": len(words), "sentences": len(sents),
        "est_duration_s": round(len(words) / wps_target, 1),
        "avg_sentence_words": round(float(np.mean(lens)), 1) if lens else 0.0,
        "hook_first_sentence": hook, "hook_first_10s": hook10,
        "filler_ratio": round(filler / max(1, len(words)), 3),
        "cta_at_end": has_cta_end,
        "notes": notes,
    }


# ------------------------------------------------------- qualidade do roteiro (estrutura)
_PAYOFF = (r"(por isso|o motivo|a resposta|o segredo é|o resultado|na prática|ou seja|conclusão|no fim das contas|"
           r"resumindo|foi assim|e funcionou|quer dizer|isso significa|significa que|então|é isso|agora você sabe|"
           r"the answer|that's why|that is why|the result|in short|so that's|bottom line|that means)")
_LOOP_MECH = {"pergunta", "lacuna de curiosidade", "contrário/mito", "prova/resultado"}


def _trigram_repeat(words: list[str]) -> float:
    tri = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    if not tri:
        return 0.0
    return 1.0 - len(set(tri)) / len(tri)


def split_glued(text: str) -> str:
    """OCR de fonte MAIÚSCULA cola palavras: quebra token com mais de 12 letras em pedaços de ~6 (≈ 1 palavra)."""
    out = []
    for tok in text.split():
        if len(tok) <= 12:
            out.append(tok)
        else:
            n = int(round(len(tok) / 6.0))
            size = -(-len(tok) // n)
            out += [tok[i:i + size] for i in range(0, len(tok), size)]
    return " ".join(out)


def count_words(text: str) -> int:
    return len(split_glued(text).split())


def script_quality(text: str, duration: float | None = None, ocr: bool = False) -> dict:
    """Nota 0..1 do ROTEIRO (sem o gancho, que é julgado à parte) + achados acionáveis em português.

    HEURÍSTICA sobre o texto: clareza das frases, especificidade, promessa x entrega, repetição,
    muletas, posição do pedido de ação (CTA) e força do final.
    """
    clean = " ".join(text.split())
    words = split_glued(clean).split() if ocr else clean.split()
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    if len(words) < 20:
        return {"score": None, "notes": ["Texto muito curto para avaliar o roteiro (menos de 20 palavras)."], "metrics": {}}
    low = clean.lower()
    lens = [len(s.split()) for s in sents]
    notes: list[dict] = []

    def note(prio, msg, action):
        notes.append({"priority": prio, "problem": msg, "action": action})

    # clareza
    long_n = sum(1 for n in lens if n > 22)
    clarity = float(np.clip(1.0 - 0.9 * long_n / max(1, len(lens)) - max(0.0, float(np.mean(lens)) - 18) / 30, 0, 1))
    if long_n:
        note(0.6, f"{long_n} frase(s) com mais de 22 palavras", "quebre em frases de até ~15 palavras; fala corrida perde o espectador")
    # especificidade
    nums = len(re.findall(r"\d", low))
    spec = float(1.0 - np.exp(-(nums / max(1, len(words)) * 100) / 1.5))
    if spec < 0.25:
        note(0.5, "roteiro vago: quase nenhum número, prazo ou exemplo concreto", "troque afirmações genéricas por um dado (\"8 meses\", \"R$ 500\", \"3 passos\")")
    # promessa x entrega
    head = score_hook_text(" ".join(words[:27]))
    opened = bool(_LOOP_MECH & set(head["signals"]))
    half = " ".join(sents[len(sents) // 2:]).lower()  # a entrega costuma vir no meio e o fim vira fecho/CTA
    closes = bool(re.search(_PAYOFF, half))
    closure = 1.0 if (not opened or closes) else 0.35
    if opened and not closes:
        note(0.6, "o começo abre uma pergunta/promessa e não identifiquei uma resposta clara na segunda metade (heurística por palavras-chave)", "se a resposta existe, deixe-a explícita (\"então…\", \"ou seja…\", \"o resultado foi…\"); se não, o espectador sente que ficou sem payoff")
    # repetição e muletas
    rep = _trigram_repeat([w.strip(".,!?").lower() for w in words])
    if rep > 0.12:
        note(0.45, f"trechos repetidos ({rep * 100:.0f}% das sequências de 3 palavras)", "corte a repetição; cada frase tem de avançar a história")
    toks = [w.strip(".,!?;:").lower() for w in words]
    filler = sum(1 for w in toks if w in _FILLER_WORDS) / len(words)
    if filler > 0.03:
        note(0.4, "muitas muletas (\"tipo\", \"né\", \"então\")", "enxugue na edição do texto")
    # CTA
    cta_idx = [i for i, s in enumerate(sents) if re.search(_CTA_END, s.lower())]
    cta_early = any(i < max(1, len(sents) // 4) for i in cta_idx)
    cta_end = any(i >= len(sents) - 2 for i in cta_idx)
    if cta_early:
        note(0.6, "pedido de inscrição/comentário logo no começo", "deixe o pedido para o fim; no início ele afasta")
    # final
    last = sents[-1].lower()
    ending = 1.0 if (cta_end or re.search(_PAYOFF, last) or "?" in last or re.search(r"coment", last)) else 0.55
    if ending < 1.0:
        note(0.5, "o final termina sem fecho, pergunta ou chamada", "termine com um fecho claro: a conclusão, uma pergunta que gere comentário ou o gancho do próximo vídeo")
    # tamanho x duração
    pace_note = None
    if duration:
        wps = len(words) / duration
        if wps > 3.6:
            note(0.5, f"texto longo demais para {duration:.0f} s (~{wps:.1f} palavras/s)", "corte ~{:.0f}% do texto ou aumente a duração".format((1 - 3.0 / wps) * 100))
        elif wps < 1.5:
            note(0.3, f"pouco texto para {duration:.0f} s (~{wps:.1f} palavras/s)", "há muito tempo sem fala; acrescente conteúdo ou corte a duração")
    score = (0.20 * clarity + 0.25 * spec + 0.20 * closure + 0.15 * (1 - min(1.0, rep * 4)) + 0.10 * (1 - min(1.0, filler * 8)) + 0.10 * ending)
    score = float(np.clip(score - (0.15 if cta_early else 0.0), 0, 1))
    score = float(np.clip(score - min(0.35, 0.08 * sum(1 for n in notes if n["priority"] >= 0.4)), 0, 1))  # nota concorda com a lista
    notes.sort(key=lambda n: -n["priority"])
    return {"score": score, "notes": notes,
            "metrics": {"palavras": len(words), "frases": len(sents), "media_palavras_frase": round(float(np.mean(lens)), 1),
                        "especificidade": round(spec, 2), "repeticao": round(rep, 2), "muletas": round(filler, 3),
                        "abre_promessa": opened, "fecha_promessa": closes}}


def script_from_audio(a: dict, seconds: int) -> dict:
    """PROXY do roteiro quando só há áudio (sem texto): cobertura de fala, regularidade, vazios e final.

    Não lê o conteúdo: só dá pistas de estrutura. Envie a legenda/roteiro (ou use --transcribe) para a análise real.
    """
    S = max(1, seconds)
    sy = a["syll_rate"][:S]
    coverage = float((sy >= 2).mean())
    cov = float(np.clip(coverage / 0.6, 0, 1))
    talk = sy[sy >= 2]
    cons = float(np.clip(1.0 - (talk.std() / (talk.mean() + 1e-9)) / 0.6, 0, 1)) if len(talk) >= 3 else 0.5
    sil = a["silent"][:S]
    mid = sil[max(0, S // 8): S - max(1, S // 8)]
    longest, run = 0, 0
    for v in mid:
        run = run + 1 if v else 0
        longest = max(longest, run)
    dead = float(np.clip(1.0 - max(0, longest - 1) / 4.0, 0, 1))
    loud = a["loud_db"][:S]
    tail = loud[int(S * 0.8):] if S >= 5 else loud
    drop = float(np.mean(loud[~sil]) - np.mean(tail[tail > -50])) if (~sil).any() and (tail > -50).any() else 0.0
    ending = float(np.clip(1.0 - max(0.0, drop - 3.0) / 10.0, 0, 1))
    notes = []
    if cov < 0.5:
        notes.append({"priority": 0.6, "problem": f"fala em só {coverage * 100:.0f}% do vídeo", "action": "preencha os vazios com narração ou corte as partes sem fala"})
    if longest >= 3:
        notes.append({"priority": 0.7, "problem": f"pausa de {longest} s no meio do vídeo", "action": "corte a pausa ou cubra com som/efeito; é onde o espectador sai"})
    if drop > 8:
        notes.append({"priority": 0.5, "problem": "a energia cai no final", "action": "termine com a frase mais forte, não com a voz morrendo"})
    if len(talk) >= 3 and cons < 0.4:
        notes.append({"priority": 0.3, "problem": "ritmo de fala muito irregular", "action": "regrave os trechos mais lentos ou acelere a edição neles"})
    score = 0.35 * cov + 0.25 * cons + 0.20 * dead + 0.20 * ending
    return {"score": float(score), "notes": notes, "proxy": True,
            "metrics": {"cobertura_fala": round(coverage, 2), "maior_pausa_s": longest, "queda_final_db": round(drop, 1)}}
