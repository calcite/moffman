"""
.. module: moffman.persistent_store
   :synopsis: Handles a persistent storage of some run-time information.
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import logging
import dbm
from contextlib import contextmanager


logger = logging.getLogger("moffman.storage")


class PersistentStorage:

    def __init__(self, storage_file_path):
        self._storage_path = storage_file_path

        if self._storage_path is None:
            logger.warning("No persistent storage configured. "
                           "Cache will only be available during run-time.")
            self._temp_storage = {}
        else:
            logger.info(
                "Persistent storage configured to: %s", self._storage_path
            )

    @contextmanager
    def _get_store(self, access_type):
        if self._storage_path is None:
            yield self._temp_storage
        else:
            with dbm.open(self._storage_path, access_type) as db:
                yield db

    def _format_key(self, *keys):
        return "-".join(keys)

    def store(self, value, *keys):
        with self._get_store("c") as db:
            db[self._format_key(*keys)] = value

    def get(self, *keys):
        try:
            with self._get_store("r") as db:
                return db[self._format_key(*keys)]
        except Exception as e:  # Must be this broad as dbm module uses strange exceptions
            return None

