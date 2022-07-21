"""
.. module: moffman.http_handler
   :synopsis: Handles the HTTP and Websocket connection to the UI.
.. moduleauthor:: "Josef Nevrly <josef.nevrly@gmail.com>"
"""

import logging
import asyncio
import pkg_resources

from aiohttp import web, ClientSession, WSMsgType, WSServerHandshakeError, \
    ClientOSError

from .utils import MoffmanError
# import sockjs

# JS_ASSETS = pkg_resources.resource_filename('moffman',
#                                             'web_ui/dist/js/')
# CSS_ASSETS = pkg_resources.resource_filename('moffman',
#                                              'web_ui/dist/css/')
# FONT_ASSETS = pkg_resources.resource_filename('moffman',
#                                               'web_ui/dist/fonts/')
# IMG_ASSETS = pkg_resources.resource_filename('moffman',
#                                              'web_ui/src/assets/')
#
# FAVICON = open(pkg_resources.resource_filename('moffman',
#                                                'web_ui/dist/favicon.ico'),
#                'rb').read()
#
# FAVICON_32 = open(pkg_resources.resource_filename(
#     'moffman', 'web_ui/dist/favicon-32x32.png'),
#     'rb').read()
#
# INDEX_FILE = open(
#     pkg_resources.resource_filename('moffman',
#                                     'web_ui/dist/index.html'), 'rb').read()
# NOTIFICATION_LOG_MESSAGE = 'log'
# NOTIFICATION_STATE_UPDATE = 'state_upd'
# NOTIFICATION_TERMINATION = "terminated"


# class WsHandler(logging.Handler):
#     """ Handler to forward logging messages over websocket."""
#
#     def __init__(self, msg_callback, level=logging.NOTSET):
#         self._msg_callback = msg_callback
#         super().__init__(level)
#
#     def emit(self, record):
#         self._msg_callback(NOTIFICATION_LOG_MESSAGE,
#                            **record.__dict__)
#

class RestApiError(MoffmanError):
    pass


RESERVATION_REQUEST = {
    "user": {
        "name": "",
        "email": "",
        },
    "approved": "",
    "start": "",
    "end": "",
    "request_dt": "",
    "office_id": ""
}


class HttpHandler:

    def __init__(self, loop,
                 # proxy_logger, log_level=logging.NOTSET,
                 on_reservation_clbk=None,
                 on_config_update_clbk=None,
                 ):

        self._loop = loop
        # self._sockjs_manager = None
        self._app = web.Application()
        self._runner = None
        self._init_router()
        self._host_addr = None
        self._host_port = None
        self._logger = logging.getLogger("moffman.REST")

        self._on_reservation_clbk = on_reservation_clbk
        self._on_config_update_clbk = on_config_update_clbk

        # Logging
        # self._proxy_logger = proxy_logger
        # self._proxy_logger.addHandler(WsHandler(self._send_notification,
        #                                         log_level))

    # def _sockjs_handler(self, msg, session):
    #     """ SockJS handler is now not doing anything because we onlu use
    #     SockJS for downstream.
    #     :param session:
    #     :return:
    #     """
    #     self._logger.debug("SockJS handler called")
    #     if msg.tp == sockjs.MSG_OPEN:
    #         self._sockjs_manager = session.manager
    #         # session.manager.broadcast("Someone joined.")
    #     elif msg.tp == sockjs.MSG_CLOSED:
    #         self._sockjs_manager = None
    #         # session.manager.broadcast("Someone left.")

    # @asyncio.coroutine
    # def _index(self, request):
    #     return web.Response(body=INDEX_FILE, content_type='text/html')
    #
    # @asyncio.coroutine
    # def _favicon(self, request):
    #     return web.Response(body=FAVICON, content_type='image/x-icon')
    #
    # @asyncio.coroutine
    # def _favicon_32(self, request):
    #     return web.Response(body=FAVICON_32, content_type='image/x-icon')
    #
    # @asyncio.coroutine
    # def _get_state(self, request):
    #     # TODO - return app state
    #     temp = self._main_app.get_state()
    #     return web.json_response(temp)
    #
    # @asyncio.coroutine
    # def _set_state(self, request):
    #     state_req = yield from request.json()
    #     try:
    #         # TODO - set app state
    #         resp = self._main_app.process_state_req(state_req)
    #         # TODO - catch proper exception
    #     except Exception as lce:
    #         self._logger.error("State request command failed: %s", str(lce))
    #         return web.json_response({}, status=500, reason=str(lce))
    #     return web.json_response(resp)

    async def _process_reservation(self, request):
        reservation_payload = await request.json()
        try:
            if self._on_reservation_clbk is not None:
                resp = await self._on_reservation_clbk(reservation_payload)
            else:
                raise RestApiError(
                    "Reservation request processing not defined."
                )
        except Exception as e:
            return web.json_response({}, status=500, reason=str(e))

        return web.Response()

    async def _update_dynamic_config(self, request):
        try:
            await self._on_config_update_clbk()
        except Exception as e:
            msg = f"Error updating dynamic config reservation: {str(e)}"
            self._logger.error(msg)
            return web.json_response({}, status=500, reason=msg)
        return web.Response()

    async def post_json(self, url, json_payload):
        async with ClientSession() as session:
            async with session.post(url, json=json_payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RestApiError(
                        f"POST request error ({url}): {resp.status} - {body}"
                    )

    def _init_router(self):
        # Basic assets
        # self._app.router.add_get('/', self._index)
        # self._app.router.add_static('/js', JS_ASSETS)
        # self._app.router.add_static('/css', CSS_ASSETS)
        # self._app.router.add_static('/fonts', FONT_ASSETS)
        # self._app.router.add_static('/api/img', IMG_ASSETS)
        # self._app.router.add_get('/favicon.ico', self._favicon)
        # self._app.router.add_get('/favicon-32x32.png', self._favicon_32)

        self._app.router.add_post('/api/v1/reservations',
                                  self._process_reservation
                                  )
        self._app.router.add_get('/api/v1/config_update',
                                 self._update_dynamic_config
                                 )
        # self._app.router.add_post('/api/command', self._set_state)

        # sockjs.add_endpoint(self._app, self._sockjs_handler, name='notifier',
        #                     prefix='/api/notifications/')

    # def _send_notification(self, msg_type, **kwargs):
    #     temp = {'type': msg_type, 'params': kwargs}
    #     self._send_ws_message(temp)
    #
    # def _send_ws_message(self, msg):
    #     if self._sockjs_manager:
    #         self._sockjs_manager.broadcast(msg)
    #
    # def send_state_update(self, state_object):
    #     self._send_notification(NOTIFICATION_STATE_UPDATE, **state_object)

    async def run(self, host='0.0.0.0', port='8080'):
        # http://aiohttp.readthedocs.io/en/stable/_modules/aiohttp/web.html?highlight=run_app

        self._app.on_shutdown.append(self._on_shutdown)
        self._logger.info("Starting HTTP server")
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        # Now run it all
        self._host_addr = host
        self._host_port = port

        site = web.TCPSite(self._runner, self._host_addr, self._host_port)
        await site.start()
        self._logger.info(
            f"HTTP server running at {self._host_addr}:{self._host_port}")

    async def _on_shutdown(self, app):
        self._logger.debug("Backend server shut down...")
        # Broadcast termination
        # self._send_notification(NOTIFICATION_TERMINATION)

    def shutdown(self):
        self._logger.debug("Shutting down the HttpHandler...")
        self._loop.create_task(self._app.shutdown())

