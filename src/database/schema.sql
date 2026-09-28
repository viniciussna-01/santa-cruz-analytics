-- Santa Cruz Analytics — esquema SQLite
-- Regra: dados ausentes ficam NULL. Nunca preenchemos com valores inventados.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY,      -- id do Sofascore
    name        TEXT NOT NULL,
    short_name  TEXT,
    slug        TEXT,
    country     TEXT
);

CREATE TABLE IF NOT EXISTS competitions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    unique_tournament_id   INTEGER NOT NULL,
    season_id              INTEGER,
    name                   TEXT NOT NULL,
    season_year            TEXT,
    UNIQUE (unique_tournament_id, season_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id                 INTEGER PRIMARY KEY,       -- event id do Sofascore
    date               TEXT,                      -- 'YYYY-MM-DD' (UTC)
    start_timestamp    INTEGER,
    competition_id     INTEGER REFERENCES competitions(id),
    competition_name   TEXT,
    round              INTEGER,
    home_team_id       INTEGER REFERENCES teams(id),
    away_team_id       INTEGER REFERENCES teams(id),
    home_team_name     TEXT,
    away_team_name     TEXT,
    home_score         INTEGER,
    away_score         INTEGER,
    status             TEXT,                      -- descrição ('Ended', 'Not started'...)
    status_type        TEXT,                      -- 'finished' | 'notstarted' | 'inprogress'
    winner_code        INTEGER,                   -- 1 casa, 2 fora, 3 empate
    venue              TEXT,
    -- perspectiva do Santa Cruz (facilita as análises)
    is_santacruz_home  INTEGER,                   -- 1/0
    santacruz_gf       INTEGER,
    santacruz_ga       INTEGER,
    santacruz_result   TEXT,                      -- 'V' | 'E' | 'D' | NULL
    opponent_id        INTEGER,
    opponent_name      TEXT,
    -- metadados de coleta
    has_lineups        INTEGER DEFAULT 0,
    has_player_stats   INTEGER DEFAULT 0,
    has_heatmap        INTEGER DEFAULT 0,
    collected_at       TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id           INTEGER PRIMARY KEY,             -- id do Sofascore
    name         TEXT NOT NULL,
    short_name   TEXT,
    position     TEXT,                            -- G | D | M | F (última conhecida)
    team_id      INTEGER,
    country      TEXT,
    dob_timestamp INTEGER
);

CREATE TABLE IF NOT EXISTS player_match_stats (
    match_id             INTEGER NOT NULL REFERENCES matches(id),
    player_id            INTEGER NOT NULL REFERENCES players(id),
    team_id              INTEGER,
    is_santacruz         INTEGER,                 -- 1/0
    position             TEXT,
    jersey               INTEGER,
    started              INTEGER,                 -- 1 titular / 0 reserva
    substitute           INTEGER,                 -- 1 se estava no banco
    minutes              INTEGER,
    rating               REAL,                    -- nota Sofascore (NULL se não houver)
    goals                INTEGER,
    assists              INTEGER,
    own_goals            INTEGER,
    shots                INTEGER,
    shots_on_target      INTEGER,
    shots_off_target     INTEGER,
    big_chances_created  INTEGER,
    big_chances_missed   INTEGER,
    xg                   REAL,
    xa                   REAL,
    passes               INTEGER,
    accurate_passes      INTEGER,
    key_passes           INTEGER,
    crosses              INTEGER,
    accurate_crosses     INTEGER,
    long_balls           INTEGER,
    accurate_long_balls  INTEGER,
    tackles              INTEGER,
    tackles_won          INTEGER,
    interceptions        INTEGER,
    clearances           INTEGER,
    blocks               INTEGER,
    duels_won            INTEGER,
    duels_lost           INTEGER,
    aerials_won          INTEGER,
    aerials_lost         INTEGER,
    ball_recoveries      INTEGER,
    touches              INTEGER,
    possession_lost      INTEGER,
    dispossessed         INTEGER,
    fouls                INTEGER,                 -- faltas cometidas
    was_fouled           INTEGER,                 -- faltas sofridas
    penalty_won          INTEGER,
    saves                INTEGER,
    saved_shots_in_box   INTEGER,
    error_led_to_shot    INTEGER,
    yellow_cards         INTEGER DEFAULT 0,       -- derivado de incidents
    red_cards            INTEGER DEFAULT 0,       -- derivado de incidents
    PRIMARY KEY (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS match_incidents (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id           INTEGER NOT NULL REFERENCES matches(id),
    minute             INTEGER,
    added_time         INTEGER,
    type               TEXT,                      -- goal | card | substitution | period | ...
    sub_type           TEXT,                      -- regular | penalty | ownGoal | yellow | red | yellowRed
    is_home            INTEGER,
    is_santacruz       INTEGER,
    player_id          INTEGER,
    player_name        TEXT,
    assist_player_id   INTEGER,
    assist_player_name TEXT,
    player_in_id       INTEGER,
    player_in_name     TEXT,
    player_out_id      INTEGER,
    player_out_name    TEXT,
    UNIQUE (match_id, minute, type, player_name, player_in_name)
);

CREATE TABLE IF NOT EXISTS match_team_stats (
    match_id      INTEGER NOT NULL REFERENCES matches(id),
    team_id       INTEGER,
    is_santacruz  INTEGER,
    period        TEXT,                           -- ALL | 1ST | 2ND
    group_name    TEXT,
    key           TEXT,
    name          TEXT,
    value         REAL,
    display       TEXT,
    PRIMARY KEY (match_id, team_id, period, key)
);

-- Mapa de calor: 1 linha por (partida, jogador). Ausência = sem dado (não inventar).
CREATE TABLE IF NOT EXISTS player_heatmap (
    match_id     INTEGER NOT NULL REFERENCES matches(id),
    player_id    INTEGER NOT NULL REFERENCES players(id),
    points_json  TEXT NOT NULL,                   -- '[{"x":..,"y":..}, ...]'
    point_count  INTEGER,
    collected_at TEXT,
    PRIMARY KEY (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS standings_snapshot (
    competition_id  INTEGER,
    team_id         INTEGER,
    team_name       TEXT,
    position        INTEGER,
    points          INTEGER,
    played          INTEGER,
    wins            INTEGER,
    draws           INTEGER,
    losses          INTEGER,
    goals_for       INTEGER,
    goals_against   INTEGER,
    snapshot_date   TEXT,
    PRIMARY KEY (competition_id, team_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

CREATE INDEX IF NOT EXISTS idx_matches_ts       ON matches(start_timestamp);
CREATE INDEX IF NOT EXISTS idx_matches_status   ON matches(status_type);
CREATE INDEX IF NOT EXISTS idx_pms_player       ON player_match_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pms_match        ON player_match_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_incidents_match  ON match_incidents(match_id);
