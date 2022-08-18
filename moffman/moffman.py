# -*- coding: utf-8 -*-
"""
.. module: moffman.moffman
   :synopsis: Main module
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import asyncio
import logging
import json
import copy

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import arrow

from .utils import sanitize_filename
from .http_handler import HttpHandler
from .calendar_handler import GoogleCalendarHandler
from .spreadsheet_handler import GoogleSpreadsheetHandler
from .dynamic_configs import ManualUserManager, OfficeManager
from .persistent_store import PersistentStorage


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

        # Persistent store
        self._persistent_store = PersistentStorage(
            self._config["general"]["storage_path"]
        )

        # Calendar handling
        self._calendar_handler = GoogleCalendarHandler(
            self._config["calendar"],
            self._service_account_key,
            self._office_manager,
            self._manual_user_manager,
            self._persistent_store,
            manual_event_process_clbk=self._on_manual_event_process,
            loop=self._loop
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
        await self._manual_user_manager.is_updated()
        await self._office_manager.is_updated()
        await self._calendar_handler.update_manual_events()

    async def _on_dynamic_config_update(self):
        await self._office_manager.update_dynamic_config()
        await self._manual_user_manager.update_dynamic_config()
        await self._calendar_handler.assert_calendars_added()

    async def _on_manual_event_process(self, event):
        logger.debug("Processing event %s from %s (%s - %s)",
                     event["summary"],
                     event["creator"]["email"],
                     event["start"]["date"],
                     event["end"]["date"]
                     )
        # Check if there is any form-filling configuration
        if (None in (self._config["forms"]["template"],
                     self._config["forms"]["url"],
                     )):
            logger.info("No form filling configuration present, "
                        "skipping manual event processing.")
            return

        # Handle the dates
        date_from = arrow.get(event["start"]["date"], self._config["calendar"][
            "date_format"])
        date_to = arrow.get(
            event["end"]["date"],
            self._config["calendar"]["date_format"]
        ).shift(**self._config["calendar"]["end_date_corrective"])

        date_approved = arrow.get(event["updated"])
        if date_approved > date_from:
            # Fix approval date so that it precedes the start date
            diff = (date_approved - date_from).days + 1
            date_approved = date_approved.shift(days=-diff)

        user_email = event["creator"]["email"]
        context = copy.deepcopy(self._manual_user_manager[user_email])

        # Convert the dates to string
        context["date_from"] = date_from.format(
            self._config["forms"]["date_format"])
        context["date_from_attachment"] = date_from.format(
            self._config["forms"]["attachment_date_format"])
        context["date_to"] = date_to.format(
            self._config["forms"]["date_format"])
        context["date_to_attachment"] = date_to.format(
            self._config["forms"]["attachment_date_format"])
        context["date_approved"] = date_approved.format(
                    self._config["forms"]["date_format"])
        context["date_approved_attachment"] = date_approved.format(
            self._config["forms"]["attachment_date_format"])

        # Format email
        email_config = self._config["forms"]["email"].copy_flat()
        if self._config["forms"]["cc_to_creator"]:
            email_config["cc"][user_email] = context["user_name"]

        email_config["subject"] = email_config["subject"].format(**context)
        email_config["contents"] = email_config["contents"].format(**context)
        if email_config["attachments"]:
            email_config["attachments"] = sanitize_filename(
                email_config["attachments"].format(**context))

        form_request = {
            "template": self._config["forms"]["template"],
            "form_data": {
                "user_id": user_email,
                "date_from": context["date_from"],
                "date_to": context["date_to"],
                "date_approved": context["date_approved"],
            },
            "result": {
                "download": False,
                "email": email_config
            }
        }

        await self._http_handler.post_json(
            self._config["forms"]["url"],
            form_request
        )

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

        # REST API
        self._http_task = self._loop.create_task(self._http_handler.run(
            host=self._config['rest_api']['addr'],
            port=self._config['rest_api']['port']
        ))

        # Scheduler
        self._scheduler.start()

        # Run initial manual event check
        self._loop.create_task(self.check_calendar_for_manual_events())

    def stop(self):
        # REST API
        self._http_handler.shutdown()

        # Scheduler
        self._scheduler.shutdown()
