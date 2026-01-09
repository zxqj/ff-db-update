from typing import Any, TypeVar
from .models import Base
from sqlalchemy import Table, MetaData, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
U = TypeVar("U", bound=Base)
def model_to_dict(model_instance: U) -> dict[str, Any]:
    """Return a dict of column-name -> value for the given SQLAlchemy declarative
    model instance. Only includes mapped column attributes (i.e., SQLAlchemy Columns),
    not relationships or other attributes.

    Example: repo.model_to_dict(player_instance)
    """
    if model_instance is None:
        return {}
    try:
        from sqlalchemy import inspect
    except Exception:
        # SQLAlchemy not available
        return {}

    try:
        mapper = inspect(model_instance.__class__)
    except Exception:
        # If a class was passed instead of an instance, try inspecting the class
        try:
            mapper = inspect(model_instance)
        except Exception:
            return {}

    result = {}
    for col in mapper.columns:
        # use getattr to fetch the attribute value from the instance
        try:
            value = getattr(model_instance, col.key)
        except Exception:
            value = None
        result[col.key] = value
    return result

T = TypeVar("T", bound=Base)


# This is something the AI did.  I'm not sure if its worth it, performance-wise.
# TODO: test speed of this versus updating everything
def bulk_upsert[T](self, model_or_table: Base, entities: list[T]) -> int:
    """Bulk upsert rows into the given model or table.

    model_or_table may be a SQLAlchemy declarative model class (has __table__) or
    a string with the table name. Rows should be a list of dicts mapping column
    names to values (including 'person_id').

    Returns the number of newly-inserted rows (based on comparing existing
    person_id values before the operation).
    """

    rows = [model_to_dict(entity) for entity in entities]
    if not rows:
        return 0
    engine = self.session.get_bind()

    # resolve table
    if isinstance(model_or_table, str):
        metadata = MetaData()
        table = Table(model_or_table, metadata, autoload_with=engine)
    else:
        table = model_or_table.__table__

    ids = [int(r['person_id']) for r in rows if r.get('person_id') is not None]
    if not ids:
        return 0

    with engine.connect() as conn:
        existing_rs = conn.execute(select(table.c.person_id).where(table.c.person_id.in_(ids)))
        existing_ids = {row[0] for row in existing_rs.fetchall()}

        new_ids = set(ids) - existing_ids
        new_count = len(new_ids)

        # build insert statement with ON CONFLICT DO UPDATE
        stmt = pg_insert(table).values(rows)

        # columns to update on conflict: all except PK and date_inserted
        update_cols = {c.name: stmt.excluded[c.name] for c in table.c if c.name not in ("person_id", "date_inserted")}

        stmt = stmt.on_conflict_do_update(index_elements=["person_id"], set_=update_cols)

        trans = conn.begin()
        try:
            conn.execute(stmt)
            trans.commit()
        except Exception:
            trans.rollback()
            raise

    return new_count
