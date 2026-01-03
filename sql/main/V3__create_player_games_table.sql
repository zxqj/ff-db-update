-- V3: create player_games table (run against the 'nba' database)

CREATE TABLE IF NOT EXISTS player_games (
    season_year            TEXT,
    player_id              INTEGER,
    player_name            TEXT,
    team_id                INTEGER,
    team_abbreviation      TEXT,
    team_name              TEXT,
    game_id                TEXT,
    game_date              DATE,
    matchup                TEXT,
    wl                     TEXT,
    min                    TEXT,
    fgm                    INTEGER,
    fga                    INTEGER,
    fg_pct                 NUMERIC,
    fg3m                   INTEGER,
    fg3a                   INTEGER,
    fg3_pct                NUMERIC,
    ftm                    INTEGER,
    fta                    INTEGER,
    ft_pct                 NUMERIC,
    oreb                   INTEGER,
    dreb                   INTEGER,
    reb                    INTEGER,
    ast                    INTEGER,
    tov                    INTEGER,
    stl                    INTEGER,
    blk                    INTEGER,
    blka                   INTEGER,
    pf                     INTEGER,
    pfd                    INTEGER,
    pts                    INTEGER,
    plus_minus             NUMERIC,
    nba_fantasy_pts        NUMERIC,
    dd2                    INTEGER,
    td3                    INTEGER,
    gp_rank                INTEGER,
    w_rank                 INTEGER,
    l_rank                 INTEGER,
    w_pct_rank             NUMERIC,
    min_rank               INTEGER,
    fgm_rank               INTEGER,
    fga_rank               INTEGER,
    fg_pct_rank            NUMERIC,
    fg3m_rank              INTEGER,
    fg3a_rank              INTEGER,
    fg3_pct_rank           NUMERIC,
    ftm_rank               INTEGER,
    fta_rank               INTEGER,
    ft_pct_rank            NUMERIC,
    oreb_rank              INTEGER,
    dreb_rank              INTEGER,
    reb_rank               INTEGER,
    ast_rank               INTEGER,
    tov_rank               INTEGER,
    stl_rank               INTEGER,
    blk_rank               INTEGER,
    blka_rank              INTEGER,
    pf_rank                INTEGER,
    pfd_rank               INTEGER,
    pts_rank               INTEGER,
    plus_minus_rank        NUMERIC,
    nba_fantasy_pts_rank   NUMERIC,
    dd2_rank               INTEGER,
    td3_rank               INTEGER,

    date_inserted          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prevent duplicate rows for the same player-game
ALTER TABLE player_games
    ADD CONSTRAINT player_games_pk PRIMARY KEY (player_id, game_id);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_player_games_player_id ON player_games (player_id);
CREATE INDEX IF NOT EXISTS idx_player_games_game_date ON player_games (game_date);

