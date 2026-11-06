---
name: viralscope
description: Analisa um vídeo curto (Short, Reel, TikTok) ou roteiro e devolve nota 0-100, gancho dos 3 primeiros segundos, sustentação, regiões Visual/Auditory/Language/Attention/Default Mode, qualidade da imagem, áudio, legenda e correções priorizadas com o trecho exato; aprende com as métricas reais do canal. Use quando o usuário pedir para analisar, pontuar, comparar ou melhorar um vídeo curto, um gancho, um roteiro ou uma thumbnail, ou perguntar se um vídeo "vai viralizar".
---

# viralscope

Analisador local (sem login, sem API paga). Código em `viralscope/`; CLI `viralscope`.

## Antes de tudo
1. Se existirem as ferramentas MCP `analyze_video` etc., use-as. Senão `viralscope --version`; se não existir: `pip install git+https://github.com/RafaelBraido/AI-VIRALITY-PREDICT` (precisa de `ffmpeg`; OCR e o resto vêm junto, sem Whisper).
2. Se o usuário não deu o caminho do vídeo/áudio, peça. Aceita MP4, MOV, WEBM, MP3, WAV, M4A.

## Comandos
- Vídeo ou áudio: `viralscope analyze A.mp4 B.mp4 C.mp4 [--platform shorts|tiktok|reels]` (vários de uma vez; ~10 s por vídeo; saída curta com VEREDITO, MELHORAR e RANKING). O texto (legenda embutida, .srt ao lado, texto na tela por OCR) é achado sozinho; `--transcript` só se o usuário tiver o roteiro. `--format completo` só se o usuário pedir regiões/cenas; `--format higgsfield` para o formato Higgsfield.
- Comparar: `viralscope compare A B` · Canal inteiro: `viralscope batch PASTA --csv rank.csv`
- Thumbnail: `viralscope image IMG` · Ganchos: `viralscope hooks ARQ` · Roteiro: `viralscope script ARQ`
- Aprender: depois que o vídeo tiver métrica real (retenção %, views em 7 dias), `viralscope learn VIDEO --target N`. Em lote: `viralscope learn --import arq.csv` (video,target). Estado: `viralscope learn --status`.

## Economia (obrigatório)
- **Uma chamada para todos os vídeos.** Não rode um por vez, não repita a análise, não leia o HTML nem o JSON: o resumo já tem o que importa.
- Responda em poucas linhas: nota, o que está bom, o que melhorar (máx. 5 itens) e o link do relatório.

## Como responder
1. Rode `analyze` (use `--json` se precisar dos números). Comece pelo **VEREDITO** em linguagem direta (ex.: "o gancho está bom, mas o roteiro precisa melhorar porque…"), diga de onde veio o texto lido, depois nota geral, pico do gancho, sustentação, regiões, cenas fracas e o link do relatório HTML.
2. Liste as 3-5 correções de maior prioridade **com o intervalo de segundos** e o que mudar.
3. Se houver probabilidade calibrada, cite junto a AUC e o n. Se não houver, diga que ainda faltam vídeos com métrica real (mínimo 20).
4. Ofereça registrar a métrica real do vídeo depois de alguns dias (`learn`), porque é assim que a ferramenta melhora no canal.

## Regras de honestidade (obrigatórias)
- A nota mede a qualidade de atenção do material com sinais do arquivo. **Não prevê views.** Nunca diga "vai viralizar" nem dê porcentagem que não venha do modelo calibrado.
- As regiões usam os nomes da Higgsfield, mas são proxies; **não medem atividade cerebral**.
- Pesos e alvos são priors. Ritmo de fala sem transcrição é proxy; texto na tela é proxy (sem OCR); rosto é Haar frontal (não pega desenho/3D).
- Não chame a API da Higgsfield nem use o login deles.
