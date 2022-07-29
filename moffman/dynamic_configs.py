"""
.. module: moffman.dynamic_configs
   :synopsis: Dynamic configuration containers for run-time config via Google sheets.
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import logging
import time
import asyncio
from itertools import chain

from .spreadsheet_handler import GoogleSpreadsheetHandler
from .utils import MoffmanError
from abc import abstractmethod, ABCMeta
from collections.abc import Mapping


logger = logging.getLogger("moffman.user_manager")


class DynamicConfigManager(Mapping, metaclass=ABCMeta):

    @abstractmethod
    def __init__(self, static_items, google_config,
                 loop=None,
                 spreadsheet_handler: GoogleSpreadsheetHandler = None):

        self._loop = loop or asyncio.get_event_loop()
        self._static_items = static_items

        # Dynamic items
        self._dynamic_items = {}
        self._google_config = google_config
        self._spreadsheet_handler = spreadsheet_handler
        self._has_dynamic_config = self._is_google_config_set()
        self._last_update = None
        self._updated = asyncio.Event()

        # Initial dynamic update
        if self._has_dynamic_config:
            self._loop.create_task(self.update_dynamic_config())
        else:
            self._updated.set()

    async def is_updated(self):
        await self._updated.wait()

    def _is_google_config_set(self):
        try:
            return ((self._spreadsheet_handler is not None) and
                    (self._google_config["sheet_id"] is not None) and
                    (self._google_config["range"] is not None)
                    )
        except KeyError:
            return False

    def __contains__(self, item):
        if item in self._static_items:
            return True

        if self._has_dynamic_config:
            return item in self._dynamic_items
        else:
            return False

    def __getitem__(self, key):
        try:
            return self._static_items[key]
        except KeyError:
            return self._dynamic_items[key]

    def __iter__(self):
        return chain(self._static_items.__iter__(),
                     self._dynamic_items.__iter__()
                     )

    def __len__(self):
        return len(self._static_items) + len(self._dynamic_items)

    @property
    def has_dynamic_config(self):
        return self._has_dynamic_config

    @property
    def requires_update_scheduling(self):
        return (self.has_dynamic_config and
                (self._google_config["update_interval"] is not None))

    @property
    def update_interval(self):
        return self._google_config["update_interval"]

    @abstractmethod
    async def update_dynamic_config(self):
        self._updated.clear()

        data = await self._spreadsheet_handler.get_range(
            self._google_config["sheet_id"],
            self._google_config["range"]
        )

        self._last_update = time.monotonic()

        # Dynamic users are reset during each update
        self._dynamic_items = {}

        return data


class ManualUserManager(DynamicConfigManager):

    def __init__(self, config,
                 loop=None,
                 spreadsheet_handler: GoogleSpreadsheetHandler = None):
        self._config = config

        # Initialize static users from config
        static_users = {}
        for static_user in self._config["user_list"]:
            static_user["user_name"] = "{first_name} {last_name}".format(
                **static_user)
            static_users[static_user["id"]] = static_user

        super().__init__(static_users, self._config["google_config"],
                         loop=loop, spreadsheet_handler=spreadsheet_handler)

        logger.info("Manual user list initialized.")

    async def update_dynamic_config(self):
        data = await super().update_dynamic_config()

        for email, first_name, last_name, emp_number in data["values"]:
            self._dynamic_items[email] = {
                "id": email,
                "first_name": first_name,
                "last_name": last_name,
                "employee_number": emp_number,
                "user_name": f"{first_name} {last_name}"
            }

        self._updated.set()
        logger.debug("User manager updated from spreadsheet.")


class OfficeManager(DynamicConfigManager):

    def __init__(self, config,
                 loop=None,
                 spreadsheet_handler: GoogleSpreadsheetHandler = None):
        self._config = config

        # Initialize static offices from config
        static_office_list = {}
        for office in self._config["office_list"]:
            static_office_list[office["name"]] = office["id"]

        super().__init__(static_office_list, self._config["google_config"],
                         loop=loop, spreadsheet_handler=spreadsheet_handler)

        logger.info("Office list initialized.")

    async def update_dynamic_config(self):
        data = await super().update_dynamic_config()

        for office_id, calendar_id in data["values"]:
            self._dynamic_items[office_id] = calendar_id

        self._updated.set()
        logger.debug("Office list updated from spreadsheet.")

