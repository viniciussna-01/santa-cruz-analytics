# Metodologia dos indicadores — Santa Cruz Analytics

Todos os números vêm do banco SQLite, alimentado pela API pública do Sofascore
(ver [PESQUISA_FASE1.md](PESQUISA_FASE1.md)). Quando um dado não existe na fonte,
ele fica `NULL`/`NaN` — **nunca** é preenchido com valor inventado.

---

## 1. Resultado, aproveitamento e forma

Perspectiva sempre do Santa Cruz:

| Indicador | Definição |
|---|---|
| `santacruz_gf` / `santacruz_ga` | gols pró / contra na partida |
| resultado | `V` se `gf > ga`, `E` se igual, `D` se `gf < ga` |
| pontos | `V=3, E=1, D=0` |
| **aproveitamento** | `100 * pontos / (jogos * 3)` |
| forma | sequência de `V/E/D` em ordem cronológica (antigo → recente) |
| média de gols | `gols_marcados / jogos` (idem sofridos) |
| clean sheet | partida com `santacruz_ga == 0` |

Recortes disponíveis: últimos 5 / 10 / 15 jogos, mandante, visitante, por
competição e por temporada. Se o recorte não tem jogos, os totais voltam `0`
e as médias voltam `None` (a interface avisa).

---

## 2. Agregados por jogador

Somatório das partidas do jogador **pelo Santa Cruz** no recorte. Colunas como
`gols`, `assistências`, `finalizações`, `passes-chave`, `desarmes`,
`interceptações`, `cartões` são somas diretas de `player_match_stats`.

- **participação em gols** = `gols + assistências`
- **gols/90** = `gols / minutos * 90` (só quando `minutos > 0`)
- **participação/90** = `(gols + assistências) / minutos * 90`
- **nota média** = média aritmética das notas Sofascore das partidas em que o
  jogador foi avaliado (partidas sem nota são ignoradas no cálculo da média,
  não contam como 0).

Cartões amarelos/vermelhos são derivados de `match_incidents` (a fonte não os
coloca nas estatísticas individuais).

---

## 3. Nota Sofascore

Usada como vem da fonte (`player_match_stats.rating`, campo
`statistics.rating` do endpoint `lineups`). Mostramos: média, melhor, pior,
média dos últimos 5 e dos últimos 10 jogos avaliados.

Competições/edições que o Sofascore não detalha ficam **sem** nota — nesses
casos o jogador aparece com `nota_media = None` para aquele recorte.

---

## 4. Índice de Performance Santa Cruz (IPS)

> O IPS é **complementar** à nota Sofascore, não a substitui. Serve para
> comparar jogadores dando peso à **função em campo**, com fórmula aberta.

### 4.1 Sub-índices (escala 0–10, por 90 minutos)

Cada estatística por 90 min é comparada a um *benchmark* fixo (o valor que
vale "10"). `escala(x, b) = min(12, max(0, x / b * 10))` (permite leve
"overflow" até 12 para destaques).

| Sub-índice | Fórmula (por 90 min) | Benchmark |
|---|---|---|
| **Ofensivo** (`off`) | `3·gols + 1·finalizações no alvo + 2·xG` | 4.0 |
| **Criação** (`cria`) | `3·assist. + 1·passes-chave + 2·grandes chances criadas + 2·xA` | 4.0 |
| **Passe** (`passe`) | `10·(0.6·min(passes certos/90 ÷ 55, 1) + 0.4·min(%acerto ÷ 0.86, 1))` | 55 passes/90 e 86% |
| **Defesa** (`defesa`) | `1.2·desarmes ganhos + 1.2·interceptações + 0.6·cortes + 1.0·bloqueios + 0.4·recuperações + 0.5·duelos ganhos` | 9.0 |
| **Disciplina/posse** (`disc`) | começa em 8; `− min(4, perdas de posse/90 ÷ 6) − min(3, faltas/90) − 2·amarelos/90 − 5·vermelhos/90`; limitado a 0–10 | — |
| **Goleiro** (`gk`) | `escala(defesas/90, 3.5)` | 3.5 defesas/90 |

### 4.2 Pesos por posição (somam 1)

| Posição | off | cria | passe | defesa | disc | gk |
|---|---:|---:|---:|---:|---:|---:|
| **G** (goleiro) | 0.00 | 0.05 | 0.20 | 0.15 | 0.15 | 0.45 |
| **D** (defensor) | 0.08 | 0.10 | 0.22 | 0.45 | 0.15 | 0.00 |
| **M** (meio-campo) | 0.18 | 0.30 | 0.25 | 0.20 | 0.07 | 0.00 |
| **F** (ataque) | 0.45 | 0.22 | 0.10 | 0.10 | 0.13 | 0.00 |

`IPS_bruto = Σ ( peso_posição[k] · sub_índice[k] )`  → escala 0–10.

### 4.3 Combinação com a nota Sofascore

```
IPS = 0.5 · nota_média_Sofascore  +  0.5 · IPS_bruto
```

- Sem nota Sofascore no recorte → `IPS = IPS_bruto` e marcamos a limitação.
- Sem minutos **e** sem nota → `IPS = None` + texto explicando (não inventamos).
- **Confiança** = `min(1, minutos_totais / (90·6))`. Abaixo de `0.4` a linha é
  marcada como "amostra pequena".

### 4.4 Limitações assumidas

- Pesos e benchmarks são **escolhas heurísticas** calibradas para a Série C /
  estadual, não um modelo estatístico validado.
- `xG`/`xA` do Sofascore só existem em parte das partidas; quando faltam,
  entram como 0 no sub-índice (reduz o valor, não infla).
- Goleiro: gols sofridos são do time, não do jogador — não entram no IPS.
- O índice **não** deve ser lido como valor de mercado nem como nota absoluta;
  é um ordenador interno e comparativo.

---

## 5. Mapa de calor

Coordenadas `{x, y}` do endpoint
`/event/{id}/player/{playerId}/heatmap` (Sofascore), guardadas em
`player_heatmap.points_json`. Escala aproximada 0–100 (x = comprimento do
campo no sentido do ataque, y = largura).

- Disponível só para jogadores que atuaram minutos relevantes; reservas que
  não entraram retornam 404 → sem linha na tabela (não inventamos pontos).
- Mapa agregado de "últimos N jogos" = concatenação dos arrays de pontos das
  partidas selecionadas.
- Visualização: densidade 2D sobre um campo desenhado em escala.

---

## 6. Análise automática ("Análise do momento")

Frases geradas por **regras**, sem IA. Cada frase só aparece se os dados que
ela cita existem. Regras atuais:

- resumo V/E/D + aproveitamento dos últimos N;
- gols pró/contra e médias;
- sequência de forma;
- clean sheets no período;
- tendência: aproveitamento dos últimos N vs. últimos 2N (limiar de 8 p.p.);
- mando de campo: diferença ≥ 15 p.p. entre casa e fora;
- líder de gols e de assistências;
- melhor nota média Sofascore (mín. 3 jogos) e, se diferente, destaque do IPS.
