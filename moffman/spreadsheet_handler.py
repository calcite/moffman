"""
.. module: moffman.spreadsheet_handler
   :synopsis: Classes and methods for handling Google Drive/Spreadsheet API
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import logging

from aiogoogle import Aiogoogle, HTTPError
from aiogoogle.auth.creds import ServiceAccountCreds
from contextlib import asynccontextmanager

from .utils import MoffmanError


logger = logging.getLogger("moffman.spreadsheets")

class SpreadsheetError(MoffmanError):
    pass


class GoogleSpreadsheetHandler:

    def __init__(self, service_account_key):
        self._google_creds = ServiceAccountCreds(
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
            **service_account_key
        )

    @asynccontextmanager
    async def _spreadsheet_api(self):
        async with Aiogoogle(
            service_account_creds=self._google_creds) as aiogoogle:
            sheets_v4 = await aiogoogle.discover("sheets", "v4")
            yield aiogoogle, sheets_v4

    async def get_range(self, spreadsheet_id: str, cell_range: str):
        async with self._spreadsheet_api() as (aiogoogle, sheets_v4):
            try:
                return await aiogoogle.as_service_account(
                    sheets_v4.spreadsheets.values.get(
                        spreadsheetId=spreadsheet_id,
                        range=cell_range
                    )
                )
            except HTTPError as e:
                msg = f"Couldn't retrieve data from spreadsheet: {str(e)}"
                logger.error(msg)
                raise SpreadsheetError(msg)

