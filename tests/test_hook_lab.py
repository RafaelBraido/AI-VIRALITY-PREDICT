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
