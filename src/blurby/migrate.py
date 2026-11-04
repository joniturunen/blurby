"""Bring an existing database's schema up to date with the model."""

import logging

import sqlalchemy as sa

from blurby.models import Data, db

logger = logging.getLogger(__name__)


def upgrade_schema():
    """Add the columns that the data table lacks, and return their names.

    Blurby's schema only grows: a release may add columns but never removes or
    changes them, so an older version still works on an upgraded database.
    db.create_all() creates a missing table but not missing columns, so this
    adds them with ALTER TABLE. Must run inside an application context.
    """
    table = Data.__table__
    inspector = sa.inspect(db.engine)
    if not inspector.has_table(table.name):
        db.create_all()
        return []
    existing = {column["name"] for column in inspector.get_columns(table.name)}
    missing = [column for column in table.columns if column.name not in existing]
    with db.engine.begin() as connection:
        for column in missing:
            definition = sa.schema.CreateColumn(column).compile(
                dialect=db.engine.dialect
            )
            connection.execute(
                sa.text(f"ALTER TABLE {table.name} ADD COLUMN {definition}")
            )
            logger.info(f"Added the column {column.name} to the {table.name} table")
    return [column.name for column in missing]
