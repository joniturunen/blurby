"""Background removal of expired secrets."""

import logging
import threading
import time
from datetime import datetime

import sqlalchemy as sa

from blurby.config import secret_ttl
from blurby.models import Data, db

logger = logging.getLogger(__name__)


def delete_expired():
    """Delete secrets past their expiry and return how many were removed.

    A secret expires at its own expires_at, or, without one (written before
    0.4.0), the default TTL after its creation, like Data.expiry. Must run
    inside an application context.
    """
    now = datetime.now()
    logger.info(f"Checking for data entries that expired before \033[1m{now}\033[0m...")
    expired = sa.or_(
        Data.expires_at < now,
        sa.and_(Data.expires_at.is_(None), Data.timestamp < now - secret_ttl()),
    )
    result = db.session.execute(db.delete(Data).where(expired))
    db.session.commit()
    if result.rowcount:
        logger.info(f"Cleaned up {result.rowcount} expired data entries!")
    return result.rowcount


def clean_up_once(app):
    """Run one cleanup pass in an application context of `app`.

    Errors are logged, not raised: an exception escaping a pass would end the
    background thread, and expired secrets would never be deleted again.
    """
    try:
        with app.app_context():
            delete_expired()
    except Exception:
        logger.exception("Cleaning up expired secrets failed, retrying next pass")


class CleanUpCrew:
    """Background thread that removes data older than the TTL."""

    def __init__(self, app):
        self.app = app
        # Define the interval in seconds for the clean_up function
        self.interval = app.config["BLURBY_CLEANUP_INTERVAL"]
        thread = threading.Thread(target=self.clean_up, args=())
        thread.daemon = True
        thread.start()

    def clean_up(self):
        while True:
            clean_up_once(self.app)
            time.sleep(self.interval)
