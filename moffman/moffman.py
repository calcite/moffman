# -*- coding: utf-8 -*-
"""
.. module: moffman.moffman
   :synopsis: Main module
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import asyncio
import logging
import json

from .http_handler import HttpHandler
from .calendar_handler import GoogleCalendarHandler


logger = logging.getLogger("moffman")



class MultiOfficeManager:

    def __init__(self, config, loop=None):
        self._config = config
        self._loop = loop or asyncio.get_event_loop()

        # Service account key
        self._service_account_key = json.load(
            open(self._config["google_api"]["service_account_key_path"])
        )

        # Calendar handling
        self._calendar_handler = GoogleCalendarHandler(
            self._config["calendar"],
            self._service_account_key,
            OFFICE_LIST,
            MANUAL_USER_LIST
        )

        # REST API
        self._http_handler = HttpHandler(
            self._loop, on_reservation_clbk=self._on_attendance_reservation
        )
        self._http_task = None

    async def _on_attendance_reservation(self, reservation_payload):
        if reservation_payload["approved"]:
            # TODO - add checking in case of non-existent event!
            await self._calendar_handler.approve_attendance_event(
                reservation_payload["user"]["name"],
                reservation_payload["request_dt"],
                reservation_payload["start"],
                reservation_payload["end"],
                reservation_payload["office_id"]
            )
        else:
            await self._calendar_handler.add_unapproved_attendance_event(
                reservation_payload["user"]["name"],
                reservation_payload["request_dt"],
                reservation_payload["start"],
                reservation_payload["end"],
                reservation_payload["office_id"]
            )

    def start(self):
        # REST API
        self._http_task = self._loop.create_task(self._http_handler.run(
            host=self._config['rest_api']['addr'],
            port=self._config['rest_api']['port']
        ))

    def stop(self):
        # REST API
        self._http_handler.shutdown()
