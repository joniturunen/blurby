"""Background removal of expired secrets."""

import logging
import threading
import time
from datetime import datetime

from blurby.config import secret_ttl
from blurby.models import Data, db

logger = logging.getLogger(__name__)


def delete_expired():
    """Delete secrets older than the TTL and return how many were removed.

    Must run inside an application context.
    """
    cutoff = datetime.now() - secret_ttl()
    logger.info(f"Checking for older than \033[1m{cutoff}\033[0m data entries...")
    result = db.session.execute(db.delete(Data).where(Data.timestamp < cutoff))
    db.session.commit()
    if result.rowcount:
        logger.info(
            f"Cleaned up {result.rowcount} data entries older than \033[1m{cutoff}\033[0m!"
        )
    return result.rowcount


def clean_up_once(app):
    """Run one cleanup pass in an application context of `app`."""
    with app.app_context():
        delete_expired()


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
