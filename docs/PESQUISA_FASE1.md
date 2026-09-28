# Santa Cruz Analytics — Pesquisa Fase 1 (endpoints reais testados)

Data dos testes: 2026-08-31
Método: `curl_cffi` com `impersonate="chrome"` (TLS fingerprint de navegador).
Host usado: `https://api.sofascore.com` (também respondem `www.sofascore.com` e `api.sofascore.app`).

## 1. Identificação do time

`GET /api/v1/search/all?q=Santa Cruz`

Resultado: **Santa Cruz (PE) = teamId `1976`**, slug `santa-cruz`, nameCode `STC`, país Brazil,
cores `#ff0000` / `#000000`. Confirmado por `GET /api/v1/team/1976`:
estádio **Estádio do Arruda**, cidade **Recife**, técnico atual **Cristian Ziani**,
`primaryUniqueTournament = Brasileirão Série C`.

Cuidado: a busca retorna vários "Santa Cruz" (RN, RS, RJ, AC, Chile, Bolívia...). O coletor
fixa o id `1976` por padrão (configurável em `.env` / config).

## 2. Endpoints validados (todos retornaram 200 com dados reais)

| Necessidade | Endpoint | Observações |
|---|---|---|
| Jogos passados | `/api/v1/team/1976/events/last/{page}` | 30 por página, campo `hasNextPage`. Página 0 = mais recentes. |
| Próximos jogos | `/api/v1/team/1976/events/next/{page}` | 6 jogos futuros no momento do teste. |
| Detalhe da partida | `/api/v1/event/{eventId}` | Traz `tournament.uniqueTournament.id`, `season.id/name`, `roundInfo`, placares, status. |
| Escalação + stats por jogador | `/api/v1/event/{eventId}/lineups` | `confirmed`, `home/away.formation`, `players[].player`, `players[].statistics`, `players[].substitute`, `missingPlayers`. |
| Estatísticas da partida | `/api/v1/event/{eventId}/statistics` | Grupos: Match overview, Shots, Attack, Passes, Duels, Defending, Goalkeeping. Itens com `key`, `homeValue`, `awayValue`. |
| Gols/assist./cartões/subs | `/api/v1/event/{eventId}/incidents` | `incidentType` in (goal, card, substitution, period...). Gol traz `player` + `assist1`. Sub traz `playerIn`/`playerOut` + `time`. Cartão traz `player` + `incidentClass` (yellow/yellowRed/red). |
| Melhores em campo | `/api/v1/event/{eventId}/best-players` | rating do time + destaque. |
| Técnicos da partida | `/api/v1/event/{eventId}/managers` | |
| Gráfico de pressão | `/api/v1/event/{eventId}/graph` | série temporal de momentum. |
| Mapa de calor por jogador | `/api/v1/event/{eventId}/player/{playerId}/heatmap` | `{ "heatmap": [ {"x":..,"y":..}, ... ] }`. Coordenadas ~0–100 (campo). |
| Posições médias | `/api/v1/event/{eventId}/average-positions` | posição média x/y por jogador. |
| Classificação | `/api/v1/unique-tournament/{utId}/season/{seasonId}/standings/total` | também `/home` e `/away`. |
| Detalhe jogador | `/api/v1/player/{playerId}` | dados cadastrais. |

Série C 2026: `uniqueTournament.id = 1281`, `season.id = 90642` (nome "Brasileiro Serie C 2026").
No teste: Santa Cruz 8º, 29 pts, 19 J, 8-5-6, 20 GF / 15 GA.

## 3. Chaves de estatística por jogador (partidas recentes, dentro de `lineups`)

`rating` (+ `ratingVersions.original`), `minutesPlayed`, `goals`, `goalAssist`, `ownGoals`,
`totalShots`, `onTargetScoringAttempt`, `shotOffTarget`, `blockedScoringAttempt`,
`bigChanceCreated`, `bigChanceMissed`, `expectedGoals`, `expectedAssists`,
`totalPass`, `accuratePass`, `keyPass`, `totalCross`, `accurateCross`,
`totalLongBalls`, `accurateLongBalls`, `accurateOwnHalfPasses`, `accurateOppositionHalfPasses`,
`totalTackle`, `wonTackle`, `interceptionWon`, `totalClearance`, `outfielderBlock`,
`duelWon`, `duelLost`, `aerialWon`, `aerialLost`, `challengeLost`,
`ballRecovery`, `touches`, `possessionLostCtrl`, `dispossessed`, `unsuccessfulTouch`,
`fouls`, `wasFouled`, `penaltyWon`, `errorLeadToAShot`,
`saves`, `savedShotsFromInsideTheBox`, `goodHighClaim`, `totalKeeperSweeper`, `accurateKeeperSweeper`.

Observações:
- Sofascore **omite chaves com valor 0** em alguns jogadores → tratar ausência como 0 ou None conforme o caso.
- **Cartões não aparecem** nas stats do jogador → derivar de `/incidents`.
- `position` do jogador vem em `players[].player.position` (G/D/M/F) e em `players[].position`.

## 4. Mapa de calor — disponibilidade real

- Disponível **por partida + jogador** para quem efetivamente jogou minutos relevantes.
- No jogo testado (15617748): **16 de 23** relacionados tinham heatmap; os 7 sem dados eram
  reservas que não entraram → HTTP **404**.
- Agregação "últimos 5 jogos" é viável concatenando os arrays de pontos.
- **Conclusão: dados reais existem.** Implementar com fallback (404 = sem heatmap, não inventar).

## 5. Rate limit / bloqueio

- 25 requisições em ~2s: todas 200, sem 429, sem bloqueio.
- Sem rate limit observável, mas o coletor usará throttle (~0.3s) e retry/backoff por segurança.
- **Bloqueio real e comprovado:** `requests`/`httpx` puros → **HTTP 403** (Cloudflare, TLS fingerprint).
  Só funciona com `curl_cffi` (`impersonate="chrome"`) ou navegador real.

## 6. O que NÃO funcionou / limitações

- `GET /api/v1/event/{id}/player/statistics` → **404** (não existe; stats de jogador vêm de `lineups`).
- Partidas antigas (Série C ≤2023, Série D, Copa do Nordeste de anos anteriores) →
  `lineups` 404 ou sem `rating`. Partidas de **2024 em diante** vêm completas.
- Amistosos ("Club Friendly Games") → normalmente sem `lineups`.
- **football-data.org** (grátis): cobre só grandes ligas; **não cobre** Série B/C/D nem Pernambucano.
  Não ajuda para o Santa Cruz no momento.
- API-Football, SportMonks, etc.: planos úteis são **pagos** → descartados por regra do projeto.

## 7. Competições no histórico recente do time (amostra de 6 páginas)

Pernambucano, Copa Betano do Brasil, Brasileirão Série C, Brasileirão Série D,
Copa do Nordeste, Club Friendly Games.

## 8. Decisão técnica (dependência)

Acesso ao Sofascore **exige** `curl_cffi` (licença MIT, gratuita, sem chave). Sem ela, 403.
Alternativa seria Playwright/navegador headless (mais pesado, não scriptável em cron simples).
Recomendação: usar `curl_cffi`.

## 9. Aviso legal

API não-oficial e não documentada; pode mudar ou bloquear a qualquer momento.
Uso pessoal/educacional. Os dados pertencem ao Sofascore e às fontes originais.
Documentar isso no README e respeitar throttle.
