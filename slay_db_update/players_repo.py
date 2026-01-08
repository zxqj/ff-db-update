from typing import List, Optional, Any
from sqlalchemy.orm import Session

from .configuration import _get_db_session
from .models import Player

class PlayerRepository:
    def __init__(self, session: Session=_get_db_session()):
        self.session = session

    def create(self, p: Any) -> Player:
        # upsert behaviour: try to insert, on conflict update (SQLAlchemy core would be required for ON CONFLICT)
        # Simpler approach: try to add and commit; if IntegrityError due to PK, merge
        from sqlalchemy.exc import IntegrityError
        try:
            self.session.add(p)
            self.session.commit()
            return p
        except IntegrityError:
            self.session.rollback()
            # merge will update existing row with values from p
            merged = self.session.merge(p)
            self.session.commit()
            return merged

    def fetchAll(self) -> List[Any]:
        return self.session.query(Player).all()

    def fetch(self, id) -> Optional[Player]:
        # use Session.get for modern SQLAlchemy
        return self.session.get(Player, id)

    def get_by_name(self, first_name: str, last_name: str) -> Optional[Player]:
        """Return the first Player matching first_name and last_name case-insensitively, or None."""
        if not first_name or not last_name:
            return None
        # Use ilike for case-insensitive exact-match semantics (no wildcard)
        return (
            self.session.query(Player)
            .filter(Player.first_name.ilike(first_name), Player.last_name.ilike(last_name))
            .first()
        )

    def fetchAllDict(self) -> List[dict]:
        """Fetch all players and return as a list of dictionaries."""
        rows = self.session.query(Player).all()
        normalized_rows = [self.model_to_dict(r) for r in rows]
        return normalized_rows

    def bulk_upsert(self, model_or_table: Any, rows: List[Any]) -> int:
        """Bulk upsert rows into the given model or table.

        model_or_table may be a SQLAlchemy declarative model class (has __table__) or
        a string with the table name. Rows can be:
          - a list of dicts (column->value)
          - a list of model instances (when model_or_table is a model class)

        Returns the number of newly-inserted rows (best-effort).
        """
        if not rows:
            return 0

        from sqlalchemy import Table, MetaData, select, tuple_
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        engine = self.session.get_bind()

        # resolve table
        if isinstance(model_or_table, str):
            metadata = MetaData()
            table = Table(model_or_table, metadata, autoload_with=engine)
        else:
            table = model_or_table.__table__

        # normalize rows to dicts if they are model instances
        normalized_rows = []
        for r in rows:
            if hasattr(r, '__table__') or hasattr(getattr(r, '__class__', None), '__table__'):
                normalized_rows.append(self.model_to_dict(r))
            elif isinstance(r, dict):
                normalized_rows.append(r)
            else:
                continue

        if not normalized_rows:
            return 0

        # handle players table (primary key 'id')
        if 'id' in table.c:
            ids = [int(r['id']) for r in normalized_rows if r.get('id') is not None]
            if not ids:
                return 0

            with engine.connect() as conn:
                existing_rs = conn.execute(select(table.c.id).where(table.c.id.in_(ids)))
                existing_ids = {row[0] for row in existing_rs.fetchall()}
                new_ids = set(ids) - existing_ids
                new_count = len(new_ids)

                stmt = pg_insert(table).values(normalized_rows)
                update_cols = {c.name: stmt.excluded[c.name] for c in table.c if c.name not in ('id', 'date_inserted')}
                stmt = stmt.on_conflict_do_update(index_elements=['id'], set_=update_cols)

                trans = conn.begin()
                try:
                    conn.execute(stmt)
                    trans.commit()
                except Exception:
                    trans.rollback()
                    raise

            return new_count

        # handle mapping table sleeper_player_ids which has (player_id, sleeper_id)
        if 'player_id' in table.c and 'sleeper_id' in table.c:
            pairs = [(int(r['player_id']), int(r['sleeper_id'])) for r in normalized_rows if r.get('player_id') is not None and r.get('sleeper_id') is not None]
            if not pairs:
                return 0

            with engine.connect() as conn:
                # select existing pairs
                stmt_sel = select(table.c.player_id, table.c.sleeper_id).where(tuple_(table.c.player_id, table.c.sleeper_id).in_(pairs))
                existing_rs = conn.execute(stmt_sel)
                existing_pairs = {(int(row[0]), int(row[1])) for row in existing_rs.fetchall()}
                new_pairs = set(pairs) - existing_pairs
                new_count = len(new_pairs)

                stmt = pg_insert(table).values(normalized_rows)
                # assume unique constraint exists on (player_id, sleeper_id)
                stmt = stmt.on_conflict_do_nothing(index_elements=['player_id', 'sleeper_id'])

                trans = conn.begin()
                try:
                    conn.execute(stmt)
                    trans.commit()
                except Exception:
                    trans.rollback()
                    raise

            return new_count

        # fallback: try insert with on conflict do nothing using any primary key available
        with engine.connect() as conn:
            stmt = pg_insert(table).values(normalized_rows)
            try:
                pk_cols = [c.name for c in table.primary_key]
                if pk_cols:
                    stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
                trans = conn.begin()
                conn.execute(stmt)
                trans.commit()
            except Exception:
                trans.rollback()
                raise

        return len(normalized_rows)
