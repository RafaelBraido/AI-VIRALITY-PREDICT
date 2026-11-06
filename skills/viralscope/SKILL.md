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

## Velocidade e economia de tokens (obrigatório)
O objetivo é **rápido e barato**: ~10 s por vídeo, resposta curta, zero chamadas à toa. Custo da análise: R$ 0 (roda local).
1. **Uma chamada para todos os vídeos**: `viralscope analyze a.mp4 b.mp4 c.mp4` (ou MCP `analyze_video` com `paths`). Nunca um por vez, nunca repetir a mesma análise.
2. **Não leia nada além da saída do comando.** Não abra o HTML, o JSON, o SRT nem os arquivos de vídeo; o resumo (~200–500 tokens por vídeo) já tem veredito, o que melhorar e o ranking.
3. **Não use `--format completo`, `--json` nem `--format higgsfield`** a menos que o usuário peça regiões, cenas ou o formato Higgsfield.
4. **Não instale nem configure nada** (Whisper, OCR, etc.): o texto é achado sozinho. Só rode `pip install` se `viralscope --version` falhar.
5. **Use `--no-ocr`** só se o usuário quiser a resposta ainda mais rápida (~5 s); avise que o roteiro/gancho falado fica estimado.
6. **Não refaça testes, não explore o código, não rode pytest**: use a ferramenta como está.
7. **Não reexplique o que a saída já diz.** Repasse o resumo; se resumir, mantenha: nota, o que está bom, os itens de MELHORAR (o quê, por quê, como) e o link do relatório.

## Gancho: o foco da resposta (obrigatório)
O gancho é o que mais decide em vídeo curto e longo. Em **todo vídeo**, depois do veredito, faça você mesmo a parte criativa que a ferramenta não faz:
1. Leia o bloco **GANCHO** da saída: o que a pessoa vê/ouve/lê em 0–3 s, mecanismos usados e faltantes, ponto de pico, frase mais forte do vídeo e o **"Texto do vídeo"**.
2. **Escreva 3 ganchos novos, concretos, na voz do criador**, usando o tema real do texto e os números dele (nunca placeholders). Varie o mecanismo (pergunta, número/contraste, contrário/mito, resultado primeiro). Máx. ~14 palavras cada.
3. Para cada um diga em uma linha **por que funciona** e marque o melhor: "Talvez este seja o melhor: … porque …".
4. Diga também o que mudar no 1º segundo (visual/som) para o gancho aparecer cedo.
5. Sempre há algo a melhorar no gancho; nunca responda só "o gancho está bom".
Como um gancho funciona: em ≤ 3 s precisa de **promessa específica + algo incompleto** (pergunta, contraste, número, resultado antes da explicação). Genérico ("hoje vou falar de…") perde para o rolar do dedo.

## Como responder
1. Rode `analyze` uma vez (saída curta). Comece pelo **VEREDITO** em linguagem direta (ex.: "o gancho está bom, mas o roteiro precisa melhorar porque…"), depois nota, o que melhorar e o link do relatório HTML. Regiões e cenas só se o usuário pedir (`--format completo`).
2. Para **cada vídeo**, diga o que pode melhorar, com **o quê, por quê e como** (a saída já traz isso por área: gancho, roteiro, imagem, áudio, retenção). Inclua o intervalo de segundos quando houver.
3. Se houver probabilidade calibrada, cite junto a AUC e o n. Se não houver, diga que ainda faltam vídeos com métrica real (mínimo 20).
4. Ofereça registrar a métrica real do vídeo depois de alguns dias (`learn`), porque é assim que a ferramenta melhora no canal.

## Regras de honestidade (obrigatórias)
- A nota mede a qualidade de atenção do material com sinais do arquivo. **Não prevê views.** Nunca diga "vai viralizar" nem dê porcentagem que não venha do modelo calibrado.
- As regiões usam os nomes da Higgsfield, mas são proxies; **não medem atividade cerebral**.
- Pesos e alvos são priors. Ritmo de fala sem transcrição é proxy; texto na tela é proxy (sem OCR); rosto é Haar frontal (não pega desenho/3D).
- Não chame a API da Higgsfield nem use o login deles.
