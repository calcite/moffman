==============================
moffman (Multi-Office Manager)
==============================

Microservice for managing team attendance in multiple offices.

Uses Google account as a data and configuration backing store.

Features
--------

* Provides REST API for registration and approval of planned attendance.
* Uses Google account as a data and configuration backing store.
* Can use `Byroapi`_ for issuing attendance approval forms.
* Runtime configurations via Google Spreadsheets.


How does it work
----------------

Moffman basically manages a shared Google calendar and handles the "approvals".
The calendar stores day-events that marks persons who intend to attend given
office.
There are two ways how to add events to the calendar:

* **REST API way** - this way is for request that come from another office
  automation workflow. It also allows approving events that has been already
  added.
* **Manual way** - this way is for members who (for any reason) cannot
  participate in another automation workflows. They can add events directly into
  the shared calendar. Only explicitly specified users (through config) can do
  this.

The output of this system is the shared Google calendar(s) (there can be several
offices each with one calendar).

In case the events are added/approved using REST API way, there are no further
actions than updating the Google calendar itself. It is assumed that the same
office automation workflow that controls moffman via the REST API would take
care of any additional steps such as approval form creation etc.

In case the events are added manually, moffman provides possibility to
automatically approve the added event and issue an approval form with
`Byroapi`_.


Installation:
-------------

.. code-block:: console

    $ pip install moffman

Usage
-----

1. Having a backing Google account
++++++++++++++++++++++++++++++++++

Moffman needs API access to an existing Google account, to use it's calendar and
spreadsheet data.
On the Google Account that is chosen for this function, following steps must be
taken:

1. `Enabling and authorizing Google Calendar API. <https://developers.google.com/calendar/api/guides/auth>`_
2. `Enabling and authorizing Google Spreadsheets API. <https://developers.google.com/sheets/api/guides/authorizing>`_
3. `Creating service account. <https://cloud.google.com/docs/authentication/production>`_

2. Configuration
++++++++++++++++

Moffman uses `Onacol`_ configuration, so any configuration parameter described
below can be configured either in the YAML file or through CLI option
or environment variable.

This documentation only describes the YAML configuration method.

To create a configuration file template, use following command::

    $ byroapi --get-config-template your_config.yaml

Typical example configuration with some template looks as follows:

.. code-block:: yaml

    general:
        # Logging level [DEBUG, INFO, WARNING, ERROR, CRITICAL]
        log_level: INFO
        # Interval to check for manually added events.
        manual_calendar_check_interval:  7200

        # Path to a persistant storage file (for storing tokens etc.). Keep null not to use persistent storage.
        storage_path: "moffman_store.dbm"

    google_api:
        # Path to the Google API credentials JSON file
        service_account_key_path: "some-service-account-343435.json"

    # External users that have access only to the Google Docs/Calendar.
    manual_users:
        # List of items in format {id: <user_email>, name: <user_name>}
        user_list: []
        google_config:
            # Google Drive ID of the Google spreadsheet file
            sheet_id: "1Id24zwRK41IDkdl34jpfx90tkY3bi4dGrl340nnldf9"

            # Google sheet range notation, see https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets/cells
            range: "Manual users!A2:B"
            # Min. interval between updates [seconds], null if automatic update is not necessary
            update_interval: null

    # Offices managed by this application
    offices:
        # List of items in format {name: <office name>, id: <Google calendar id>}
        office_list: []
        google_config: "1Id24zwRK41IDkdl9dfsdfstkY3bi4dG340nnldf9"

    # Byroapi (https://github.com/calcite/byroapi) form-filler configuration
    forms:
        template: "Your_Template"
        url: "http://your-byroapi-instance.com/api/v1/form"
        date_format: "DD.MM.YYYY"
        email:
            from:
                moffman-administrator@macme.com: "Moffman admin"
            to: "form-recipient-email@acme.com"
            cc:
                moffman-administrator@macme.com: "Moffman admin"
            subject: "Some office attendance - {user_name} ({date_from} - {date_to})"
            contents: "Hey, here's the form regarding someone's office attendance ({user_name}: {date_from} - {date_to}).\n\nDěkuji předem za zpracování,\n\nJosef"

    calendar:
        # Event colors (defined as indexes to the Google calendar color palette)
        colors:
            # Color of approval-pending registration event.
            unapproved:
            # Color of approved registration event.
            approved:

        # Checking range for event lookup in the manual update. The values are relative to the time of update, and are defined as Arrow shift arguments (https://arrow.readthedocs.io/en/latest/#arrow.arrow.Arrow.shift)
        checking_range:
            min:
                weeks: -1
            max:
                weeks: 2
        date_format: "YYYY-MM-DD"
        end_date_corrective:
            days: -1

    rest_api:  # Configuration of the REST API endpoint
        addr: 0.0.0.0
        port: 8080

as you can see, several configuration items include a ``google_config`` section.
The purpose of this section is to refer to a range in an defined
Google Spreadsheet, that contains configuration in expected format.o

This is the way how to dynamically update some configuration details without
restarting the service.

Configuration data from Google Spreadsheet are downloaded to the moffman
configuration in two ways:

1. Using a fixed-time interval specified in
``google_config:min_update_interval`` for each section.
2. Manually initiating updat via REST API - by doing GET on
``/api/v1/config_update``.

3. Usage
++++++++

Moffman provides a simple CLI. To run as a server::

    $ moffman --config your_config.yaml

It's also possible to convey the configuration via ENV variables (see `Onacol`_).

Moffmann runs as a background service, receiving data on it's REST intreface,
and updating/manipulating data on Google calendar.

Following API endpoints are currently provided:

* ``POST /api/v1/reservations`` - accepts JSON reservations in following form:

.. code-block:: json

    {
	"user": {
        "name": "Some User",
        "email": "user@nacme.com"
        },
    "approved": true,
    "start": "2022-06-28",
    "end": "2022-06-29",
    "request_dt": "11:38:00 2020/06/25",
    "office_id": "your-office"
    }

* ``GET /api/v1/config_update`` - empty GET to force configuration reload from
  Google Spreadsheet.


.. _Onacol: https://github.com/calcite/onacol
.. _Byroapi: https://github.com/calcite/byroapi
