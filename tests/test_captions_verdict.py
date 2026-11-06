import shutil
import subprocess

import pytest

from conftest import SR, ff, needs_ffmpeg, speech_like, write_wav
from viralscope import captions, scoring, text

pytestmark = needs_ffmpeg

SRT = ("1\n00:00:00,400 --> 00:00:03,000\nVocê está errando isso há 8 meses?\n\n"
       "2\n00:00:03,000 --> 00:00:07,500\nEu testei 3 métodos e o segundo dobrou as views em 7 dias. "
       "Por isso o motivo é simples: o gancho decide tudo. Comenta qual você usa.\n")


def test_ocr_reads_burned_in_text_without_any_input(vids):
    r = scoring.analyze(vids["caption"])
    assert r["transcript"]["source"] == "texto lido na tela (OCR)"
    t = r["transcript"]["text"].upper().replace(" ", "")
    assert "ERRANDO" in t and "MESES" in t


def test_no_text_no_ocr_result_for_clean_video(vids):
    r = scoring.analyze(vids["nocaption"])
    assert r["transcript"] is None and r["warnings"] and "estimado só pelo áudio" in r["warnings"][0]


def test_sidecar_srt_is_found_next_to_video(vids, tmp_path):
    v = tmp_path / "meu.mp4"
    shutil.copy(vids["speech"], v)
    (tmp_path / "meu.srt").write_text(SRT, encoding="utf-8")
    r = scoring.analyze(str(v))
    assert r["transcript"]["source"].startswith("arquivo .srt")
    assert r["language_source"] == "transcrição" and r["script"]["score"] is not None


def test_embedded_subtitle_track_is_read(vids, tmp_path):
    srt = tmp_path / "s.srt"
    srt.write_text(SRT, encoding="utf-8")
    out = tmp_path / "emb.mp4"
    ff("-i", vids["speech"], "-i", str(srt), "-c", "copy", "-c:s", "mov_text", str(out))
    r = scoring.analyze(str(out))
    assert r["transcript"]["source"] == "legenda embutida no arquivo"
    assert "gancho decide" in r["transcript"]["text"]


def test_explicit_transcript_wins_over_everything(vids, tmp_path):
    v = tmp_path / "x.mp4"
    shutil.copy(vids["caption"], v)
    (tmp_path / "x.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nlixo do sidecar sem importância aqui\n", encoding="utf-8")
    r = scoring.analyze(str(v), transcript=SRT)
    assert r["transcript"]["source"] == "texto enviado por você"


def test_verdict_separates_good_hook_from_weak_script(vids):
    bad_script = ("1\n00:00:00,400 --> 00:00:03,000\nVocê está errando isso há 8 meses?\n\n"
                  "2\n00:00:03,000 --> 00:00:07,500\nEntão, tipo, é uma coisa legal que é muito importante né e que muda tudo "
                  "de um jeito que você nem imagina porque é uma coisa legal. Tipo, é uma coisa legal.\n")
    r = scoring.analyze(vids["dyn"], transcript=bad_script)
    by = {v["area"]: v for v in r["verdicts"]}
    assert by["roteiro"]["label"] in ("ok", "fraco") and by["roteiro"]["actions"]
    good = scoring.analyze(vids["dyn"], transcript=SRT)
    gby = {v["area"]: v for v in good["verdicts"]}
    assert gby["roteiro"]["score"] > by["roteiro"]["score"] + 0.2


def test_verdict_text_is_plain_portuguese_and_gendered(vids):
    from viralscope import report
    r = scoring.analyze(vids["flat"])
    txt = report.to_text(r)
    assert txt.startswith("VEREDITO") and "A imagem" in txt and "precisa melhorar" in txt
    assert "A imagem está bom" not in txt and "Comece por:" in txt


def test_scenes_follow_cuts_and_flag_weak_ones(vids):
    r = scoring.analyze(vids["slow"])
    assert len(r["scenes"]) >= 2
    assert r["scenes"][0]["label"] != "forte" and "parada" in r["scenes"][0]["note"]
    assert r["scenes"][-1]["engagement"] > r["scenes"][0]["engagement"]


def test_audio_only_mp3_wav(tmp_path):
    wav = tmp_path / "voz.wav"
    write_wav(wav, speech_like(8.0, 5.5, 0.4))
    mp3 = tmp_path / "voz.mp3"
    ff("-i", str(wav), str(mp3))
    for f in (wav, mp3):
        r = scoring.analyze(str(f))
        assert r["mode"] == "audio" and {v["area"] for v in r["verdicts"]} == {"gancho", "roteiro", "áudio"}
        assert 0 <= r["overall"] <= 100
    r = scoring.analyze(str(wav), transcript=SRT)
    assert r["script"]["score"] is not None and r["hook_text"]["score"] > 0.4


def test_audio_only_cli(tmp_path, capsys):
    from viralscope.cli import main
    wav = tmp_path / "v.wav"
    write_wav(wav, speech_like(6.0, 5.5, 0.4))
    assert main(["analyze", str(wav)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("VEREDITO") and "Só áudio" in out


def test_ocr_cues_merge_repeated_text(vids):
    cues = captions.ocr_cues(vids["caption"], 8.0)
    assert cues and len(cues) <= 2 and cues[0][1] - cues[0][0] > 4
