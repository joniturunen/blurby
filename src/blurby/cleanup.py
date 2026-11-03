"""Background removal of expired secrets."""

import logging
import threading
import time
from datetime import datetime

from blurby.config import secret_ttl
from blurby.models import Data, db

logger = logging.getLogger(__name__)


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
            with self.app.app_context():
                ttl = secret_ttl()
                logger.info(
                    f"Checking for older than \033[1m{datetime.now() - ttl}\033[0m data entries..."
                )
                # if there are entries in the database that are older than the TTL remove them
                if Data.query.filter(Data.timestamp < datetime.now() - ttl).all():
                    logger.info(
                        f"Found data entries that are older than \033[1m{datetime.now() - ttl}\033[0m, deleting..."
                    )
                    Data.query.filter(Data.timestamp < datetime.now() - ttl).delete()
                    db.session.commit()
                    # write log entry
                    logger.info("Cleaned up old data entries!")
            time.sleep(self.interval)
