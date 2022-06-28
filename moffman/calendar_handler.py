"""
.. module: moffman.calendar_handler
   :synopsis: Classes and methods for handling Google Calendar API.
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import logging

from aiogoogle import Aiogoogle, HTTPError
from aiogoogle.auth.creds import ServiceAccountCreds
import uuid
from contextlib import asynccontextmanager
import arrow

from .dynamic_configs import ManualUserManager, OfficeManager


logger = logging.getLogger("moffman.calendar")


def get_event_id(user: str, request_dt: str, start: str, end: str):
    """ Generate UUID sutiable as event ID, that is based on the input data.
        That way we can identify unique events for modification without
        search.
        For uniqueness, the timestamp of the request is used.

    :param user:  User name.
    :param request_dt:  Timestamp of the request.
    :param start: Timestamp of the event start.
    :param end: Timestamp of the event end.
    :return:
    """
    tmp = ".".join([user, request_dt, start, end])
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, tmp)).replace("-", "")


def search_range(min_time, max_time):
    """ Produce tuple of dates that define a range for event retrieval.

    :param min_time: Lower bound of the range relative to the now-date.
    :param max_time: Upper bound of the range relative to the now-date.
    :return: Tupe of RFC3339 date strings.
    """
    a = arrow.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return str(a.shift(**min_time)), str(a.shift(**max_time))


class GoogleCalendarHandler:
    EVENT_PROCESSED = "event_processed"

    def __init__(self, config, service_account_key, office_list,
                 manual_user_list: ManualUserManager):

        self._config = config
        self._manual_user_list = manual_user_list
        self._office_list = office_list

        # Initialize credentials
        self._google_creds = ServiceAccountCreds(
            scopes=[
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events"
            ],
            **service_account_key
        )

        # Other defaults
        # self._calendar_id = self._config["calendar_id"]

        # Sync token
        self._int_sync_tokens = {office: None for office in
                                 self._office_list.keys()}

        # TODO - check if all calendars in the office list are added in the
        #        service_accounts_list and are accesible. If not, add.

    def _get_sync_token(self, office):
        # TODO - handle persistence
        return self._int_sync_tokens[office]

    def _store_sync_token(self, office, token):
        # TODO - handle persistence
        self._int_sync_tokens[office] = token

    def _is_event_unprocessed(self, event):
        try:
            return event["extendedProperties"]["private"][self.EVENT_PROCESSED]
        except KeyError:
            return False

    def _is_event_manual(self, event):
        try:
            event["extendedProperties"]["private"][self.EVENT_PROCESSED]
            return False
        except KeyError:
            return True

    def _is_event_from_registered_user(self, event):
        return event["creator"]["email"] in self._manual_user_list

    @asynccontextmanager
    async def _calendar_api(self):
        async with Aiogoogle(
           service_account_creds=self._google_creds) as aiogoogle:
            calendar_v3 = await aiogoogle.discover("calendar", "v3")
            yield aiogoogle, calendar_v3

    async def _add_event(self, event_name, start_date, end_date, calendar,
                         event_id=None, color_id=None,
                         extended_properties=None):
        async with self._calendar_api() as (aiogoogle, calendar_v3):
            event = {
                "summary": event_name,
                "start": {
                    "date": start_date,
                },
                "end": {
                    "date": end_date,
                }
            }

            if event_id is not None:
                event["id"] = event_id

            if color_id is not None:
                event["colorId"] = color_id

            if extended_properties is not None:
                event["extendedProperties"] = {"private": extended_properties}

            return await aiogoogle.as_service_account(
                calendar_v3.events.insert(calendarId=calendar, json=event))

    async def _modify_event(self, event_id, start_date, end_date, calendar,
                            **modifications):
        async with self._calendar_api() as (aiogoogle, calendar_v3):
            return await aiogoogle.as_service_account(
                calendar_v3.events.patch(calendarId=calendar, eventId=event_id,
                                         json=modifications))

    async def _get_colors(self):
        async with self._calendar_api() as (aiogoogle, calendar_v3):
            return await aiogoogle.as_service_account(calendar_v3.colors.get())

    async def _get_events(self, calendar_id, **params):
        async with self._calendar_api() as (aiogoogle, calendar_v3):
            return await aiogoogle.as_service_account(
                calendar_v3.events.list(calendarId=calendar_id, **params))

    async def add_unapproved_attendance_event(self, person, request_dt,
                                              start_date, end_date, office):
        person_name = f"({person})"
        event_id = get_event_id(person, request_dt, start_date, end_date)
        extended_properties = {self.EVENT_PROCESSED: False}
        return await self._add_event(person_name, start_date, end_date,
                                     self._office_list[office],
                                     event_id=event_id,
                                     color_id=self._config["colors"][
                                         "unapproved"],
                                     extended_properties=extended_properties
                                     )

    async def approve_attendance_event(self, person, request_dt, start_date,
                                       end_date, office):
        person_name = person
        event_id = get_event_id(person, request_dt, start_date, end_date)
        return await self._modify_event(event_id, start_date, end_date,
                                        self._office_list[office],
                                        summary=person_name,
                                        colorId=self._config["colors"][
                                            "approved"],
                                        extendedProperties={"private": {
                                            self.EVENT_PROCESSED: True}}
                                        )

    async def update_manual_events(self):
        for office in self._office_list.keys():
            await self.process_new_manual_events(office)

    async def process_new_manual_events(self, office):
        search_params = {}

        # If we have sync token, let's use it
        sync_token = self._get_sync_token(office)
        if sync_token is not None:
            search_params["syncToken"] = sync_token

        while True:
            if not search_params:
                # We don't have token, so let's use time range
                time_min, time_max = search_range(
                    self._config["checking_range"]["min"],
                    self._config["checking_range"]["max"]
                )
                search_params = {"timeMin": time_min, "timeMax": time_max}

            try:
                print(search_params)
                events = await self._get_events(
                    self._office_list.get_id(office), **search_params
                )
                print("searched")
                break
            except HTTPError as e:
                print(e)
                if e.res.status_code == 410:
                    # Token is expired, let's repeat with time range
                    search_params = {}
                else:
                    # TODO raise some other exception
                    break

        # Let's get new sync token
        new_sync_token = events["nextSyncToken"]

        # Now we have a list of events, let's get unprocessed ones
        # Filter out events that are not processed
        manual_events = filter(self._is_event_manual, events["items"])

        # Filter out events that are from registered sources
        manual_events = filter(self._is_event_from_registered_user,
                               manual_events)

        for event in manual_events:
            # TODO: Do the actual form-filling
            print(event)

            # TODO: Update the event so that it's marked as processed

        # Update sync token (now disabled for debug)
        # self._store_sync_token(office, new_sync_token)
