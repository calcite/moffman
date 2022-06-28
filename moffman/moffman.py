# -*- coding: utf-8 -*-
"""
.. module: moffman.moffman
   :synopsis: Main module
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import asyncio
import logging
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .http_handler import HttpHandler
from .calendar_handler import GoogleCalendarHandler
from .spreadsheet_handler import GoogleSpreadsheetHandler
from .dynamic_configs import ManualUserManager, OfficeManager


logger = logging.getLogger("moffman")


class MultiOfficeManager:

    def __init__(self, config, loop=None):
        self._config = config
        self._loop = loop or asyncio.get_event_loop()

        # Service account key
        self._service_account_key = json.load(
            open(self._config["google_api"]["service_account_key_path"])
        )

        # Spreadsheet handling
        self._spreadsheet_handler = GoogleSpreadsheetHandler(
            self._service_account_key
        )

        # Manual users
        self._manual_user_manager = ManualUserManager(
            self._config["manual_users"],
            loop=loop,
            spreadsheet_handler=self._spreadsheet_handler
        )

        # Offices
        self._office_manager = OfficeManager(
            self._config["offices"],
            loop=loop,
            spreadsheet_handler=self._spreadsheet_handler
        )

        # Calendar handling
        self._calendar_handler = GoogleCalendarHandler(
            self._config["calendar"],
            self._service_account_key,
            self._office_manager,
            self._manual_user_manager
        )

        # REST API
        self._http_handler = HttpHandler(
            self._loop,
            on_reservation_clbk=self._on_attendance_reservation,
            on_config_update_clbk=self._on_dynamic_config_update
        )
        self._http_task = None

        # Scheduler
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.check_calendar_for_manual_events,
            'interval',
            seconds=self._config["general"]["manual_calendar_check_interval"],
        )

        if self._office_manager.requires_update_scheduling:
            self._scheduler.add_job(
                self._office_manager.update_dynamic_config,
                'interval',
                seconds=self._office_manager.update_interval
            )

        if self._manual_user_manager.requires_update_scheduling:
            self._scheduler.add_job(
                self._manual_user_manager.update_dynamic_config,
                'interval',
                seconds=self._manual_user_manager.update_interval
            )

    async def check_calendar_for_manual_events(self):
        logger.debug("Running manual event update task.")
        await self._calendar_handler.update_manual_events()

    async def _on_dynamic_config_update(self):
        await self._office_manager.update_dynamic_config()
        await self._manual_user_manager.update_dynamic_config()
        await self._calendar_handler.assert_calendars_added()

    async def _on_attendance_reservation(self, reservation_payload):
        try:
            if reservation_payload["approved"]:
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
        except Exception as e:
            user = reservation_payload.get("user", {"name": "Unknown"})
            logger.error(f"Error processing attendance reservation "
                         f"{user['name']}: {str(e)}"
                         )
            raise e

    def start(self):

        # Run initial manual event check
        self._loop.create_task(self.check_calendar_for_manual_events())

        # REST API
        self._http_task = self._loop.create_task(self._http_handler.run(
            host=self._config['rest_api']['addr'],
            port=self._config['rest_api']['port']
        ))

        # Scheduler
        self._scheduler.start()

    def stop(self):
        # REST API
        self._http_handler.shutdown()

        # Scheduler
        self._scheduler.shutdown()
