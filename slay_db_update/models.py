from sqlalchemy import (
    Column,
    Integer,
    Text,
    Boolean,
    DateTime,
    Numeric,
    func,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'

    date_inserted = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    to_year = Column(Integer, nullable=True)
    from_year = Column(Integer, nullable=True)
    stats_timeframe = Column(Text, nullable=True)
    ast = Column(Numeric, nullable=True)
    reb = Column(Numeric, nullable=True)
    pts = Column(Numeric, nullable=True)
    roster_status = Column(Text, nullable=True)
    draft_number = Column(Integer, nullable=True)
    draft_round = Column(Integer, nullable=True)
    draft_year = Column(Integer, nullable=True)
    country = Column(Text, nullable=True)
    college = Column(Text, nullable=True)
    weight = Column(Text, nullable=True)
    height = Column(Text, nullable=True)
    position = Column(Text, nullable=True)
    jersey_number = Column(Text, nullable=True)
    team_abbreviation = Column(Text, nullable=True)
    team_name = Column(Text, nullable=True)
    team_city = Column(Text, nullable=True)
    is_defunct = Column(Boolean, nullable=True)
    team_slug = Column(Text, nullable=True)
    team_id = Column(Integer, nullable=True)
    player_slug = Column(Text, nullable=True)
    first_name = Column(Text, nullable=True)
    last_name = Column(Text, nullable=True)
    id = Column(Integer, primary_key=True)

    def to_dict(self):
        return {
            'date_inserted': self.date_inserted,
            'to_year': self.to_year,
            'from_year': self.from_year,
            'stats_timeframe': self.stats_timeframe,
            'ast': self.ast,
            'reb': self.reb,
            'pts': self.pts,
            'roster_status': self.roster_status,
            'draft_number': self.draft_number,
            'draft_round': self.draft_round,
            'draft_year': self.draft_year,
            'country': self.country,
            'college': self.college,
            'weight': self.weight,
            'height': self.height,
            'position': self.position,
            'jersey_number': self.jersey_number,
            'team_abbreviation': self.team_abbreviation,
            'team_name': self.team_name,
            'team_city': self.team_city,
            'is_defunct': self.is_defunct,
            'team_slug': self.team_slug,
            'team_id': self.team_id,
            'player_slug': self.player_slug,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'id': self.id,
        }

class SleeperPlayer(Base):
    __tablename__ = 'sleeper_player_ids'

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id', ondelete='CASCADE'), nullable=False)
    sleeper_id = Column(Integer, nullable=False)
    date_inserted = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
