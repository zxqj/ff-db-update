from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    Date,
    DateTime,
    func,
    PrimaryKeyConstraint,
)

from .models import Base

class GameStats(Base):
    __tablename__ = "player_games"
    __table_args__ = (PrimaryKeyConstraint("player_id", "game_id"),)

    season_id = Column(String(5), nullable=True)
    player_id = Column(Integer, nullable=False)
    team_id = Column(Integer, nullable=True)
    team_name = Column(Text, nullable=True)
    team_code = Column(Text, nullable=True)
    game_id = Column(String(50), nullable=False)
    game_date = Column(Date, nullable=True)
    matchup = Column(Text, nullable=True)
    wl = Column(Text, nullable=True)
    min = Column(Text, nullable=True)

    fgm = Column(Integer, nullable=True)
    fga = Column(Integer, nullable=True)
    fg_pct = Column(Numeric, nullable=True)

    fg3m = Column(Integer, nullable=True)
    fg3a = Column(Integer, nullable=True)
    fg3_pct = Column(Numeric, nullable=True)

    ftm = Column(Integer, nullable=True)
    fta = Column(Integer, nullable=True)
    ft_pct = Column(Numeric, nullable=True)

    oreb = Column(Integer, nullable=True)
    dreb = Column(Integer, nullable=True)
    reb = Column(Integer, nullable=True)

    ast = Column(Integer, nullable=True)
    tov = Column(Integer, nullable=True)
    stl = Column(Integer, nullable=True)
    blk = Column(Integer, nullable=True)
    pf = Column(Integer, nullable=True)
    pts = Column(Integer, nullable=True)

    plus_minus = Column(Numeric, nullable=True)
    date_inserted = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

