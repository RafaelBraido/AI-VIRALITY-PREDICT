from viralscope import text

CUES = [(0.0, 3.0, "PAI, UMA FOTO DO MEU CELULAR PESA MAIS QUE O MARIO INTEIRO"),
        (3.0, 6.0, "O Super Mario original tem uns quarenta quilobytes."),
        (6.5, 9.0, "Mas por que isso acontece, você sabe?"),
        (30.0, 34.0, "Ou seja, uma foto tem 3 MB e o jogo tinha 40 KB, então cabia tudo.")]


def lab(opening=None):
    full = " ".join(t for _, _, t in CUES)
    return text.hook_lab(opening or CUES[0][2], full, CUES, [(0.0, "40KB 3 MB")], 50)


def test_numbers_come_from_title_first_and_no_bare_4k():
    full = "4K tem uma resolução enorme. " + " ".join(t for _, _, t in CUES)
    r = text.hook_lab(CUES[0][2], full, CUES, [(0.0, "40KB 3 MB")], 50)
    assert r["numbers"][:2] == ["40KB", "3 MB"] and "4K" not in r["numbers"]


def test_finds_stronger_line_that_appears_late():
    r = lab()
    assert r["strongest"] and r["strongest"]["t"] >= 2.0 and "você sabe" in r["strongest"]["text"]


def test_ideas_use_real_material_or_show_placeholders():
    r = lab()
    assert 1 <= len(r["ideas"]) <= 3
    for i in r["ideas"]:
        assert i["fill"] == ("[" in i["text"])  # sem material, só fórmula com lacuna; nunca tema inventado
    assert any("40KB contra 3 MB" in i["text"] for i in r["ideas"])
    assert r["material"]["text_start"].startswith("PAI")


def test_missing_mechanisms_listed():
    r = lab("PAI, UMA FOTO PESA MAIS QUE O MARIO")
    assert "pergunta" in r["missing"] or "contrário/mito" in r["missing"]


def test_plan10_gaps_sum_to_distance_from_100():
    from viralscope import plan10
    res = {"overall": 60.0, "components": {"hook": 0.5, "image": 0.8, "script": 0.5, "audio_tech": 0.9},
           "weights": {"hook": 0.28, "image": 0.08, "script": 0.10, "audio_tech": 0.04}, "verdicts": []}
    g = plan10.video_gaps(res)
    w = res["weights"]
    # a nota real do dict é só um rótulo; os ganhos vêm dos componentes e somam 100 - nota recalculada
    base = 100 * sum(w[k] * res["components"][k] for k in w) / sum(w.values())
    assert abs(sum(r["gain"] for r in g["rows"]) - (100 - base)) < 1.0
    assert g["rows"][0]["area"] == "gancho" and g["at_90"] > base and g["at_100"] == 100.0


def test_script_filter_flags_weak_and_passes_strong():
    from viralscope import plan10
    fraco = "Hoje vou falar sobre piscinas. " + "Piscina e uma coisa legal que muita gente tem em casa e gosta de usar. " * 6
    forte = ("Cavei um buraco e enchi de água. Em 1 dia a piscina sumiu. Por quê? A terra chupa a água e o fundo vira barro. "
             "Com uma lona, o furo de 1 pedrinha esvaziou 5000 litros em 8 horas. O motivo: a lona não segura peso. "
             "Ou seja, piscina de verdade tem parede de concreto com ferro de 10 mm. A bomba filtra 3 vezes por dia. "
             "No fim, piscina não é sobre água, é sobre segurar a água. O que a gente constrói agora? Comenta aí.")
    f1, f2 = plan10.script_filter(fraco), plan10.script_filter(forte)
    assert f1["score_10"] < f2["score_10"] and not f1["approved"]
    assert any(not c["ok"] and c["como"] for c in f1["criteria"])


def test_verdict10_lines():
    from viralscope import plan10
    g = {"score_10": 7.4, "rows": [{"area": "gancho"}, {"area": "roteiro"}]}
    f = {"score_10": 5, "approved": False, "criteria": [{"criterio": "x", "ok": False}]}
    assert "Ainda não" in plan10.lines_verdict10(g, f) and "5/10" in plan10.lines_verdict10(g, f)
    assert "Sim" in plan10.lines_verdict10({"score_10": 10.0, "rows": []}, None)
    assert "REPROVADO" in plan10.lines_filter_short(f)[0]


def test_opening_visual_demo_and_reveal():
    import numpy as np
    from viralscope import plan10
    S = 12
    base = {"cuts": np.zeros(S), "motion": np.full(S, 0.01), "hist_dist": np.full(S, 0.02), "text_ratio": np.zeros(S)}
    parado = plan10.opening_visual(base, S)
    assert not parado["demo_3s"] and not parado["reveal_ok"]
    v = {k: x.copy() for k, x in base.items()}
    v["motion"][:3] = 0.2          # ação já nos 3 primeiros segundos
    v["hist_dist"][4] = 0.9        # sobreposição/mudança nova aos 4 s
    r = plan10.opening_visual(v, S)
    assert r["demo_3s"] and r["reveal_events"] == [4]


def test_generic_intro_is_auto_rejected():
    from viralscope import plan10
    txt = ("Fala galera, hoje eu vou mostrar um bug. " + "A hitbox do jogo falha em 3 casos e o personagem atravessa a parede em 2 segundos. " * 7
           + "Ou seja, o motivo é a colisão. O que a gente testa agora? Comenta aí.")
    f = plan10.script_filter(txt)
    assert f["generic_opening"] and not f["approved"]
    assert "REJEITADO" in "\n".join(plan10.lines_filter(f))
