"""
.. module: moffman.dynamic_configs
   :synopsis: Dynamic configuration containers for run-time config via Google sheets.
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import logging
import time

from .spreadsheet_handler import GoogleSpreadsheetHandler


logger = logging.getLogger("moffman.user_manager")


class ManualUserManager:

    def __init__(self, config,
                 spreadsheet_handler: GoogleSpreadsheetHandler = None):
        self._config = config

        # Initialize static users
        self._static_users = {}
        for static_user in self._config["user_list"]:
            self._static_users[static_user["id"]] = static_user["name"]

        # Dynamic users
        self._dynamic_users = {}
        self._spreadsheet_handler = spreadsheet_handler
        self._is_dynamic_config = self._is_google_config_set()

        # Dynamic update
        self._last_update = None
        if self._is_dynamic_config:
            await self._update_dynamic_config()

    async def check_user(self, user):
        if user in self._static_users:
            return True

        if self._is_dynamic_config:
            # Check dynamic config
            if ((time.monotonic() - self._last_update) > self._config[
               "google_config"]["update_interval"]):
                await self._update_dynamic_config()

            return user in self._dynamic_users

        else:
            return False

    def _is_google_config_set(self):
        try:
            return ((self._spreadsheet_handler is not None) and
                    (self._config["google_config"]["sheet_id"] is not None) and
                    (self._config["google_config"]["range"] is not None)
                    )
        except KeyError:
            return False

    async def _update_dynamic_config(self):
        data = await self._spreadsheet_handler.get_range(
            self._config["google_config"]["sheet_id"],
            self._config["google_config"]["range"]
        )

        # Dynamic users are reset during each update
        self._dynamic_users = {}

        for name, email in data["values"]:
            self._dynamic_users[email] = name

        self._last_update = time.monotonic()
        print(self._dynamic_users)

        logger.debug("User manager updated from spreadsheet.")


class OfficeManager:

    def __init__(self, config,
                 spreadsheet_handler: GoogleSpreadsheetHandler = None):
        self._config = config

        # Static list
        self._static_office_list = {}
        for office in self._config["office_list"]:
            self._static_office_list[office["name"]] = office["id"]

    @property
    def office_names(self):
        return list(self._static_office_list.keys())

    def get_id(self, office):
        return self._static_office_list[office]



