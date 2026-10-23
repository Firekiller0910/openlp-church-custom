##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2025 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
The :mod:`~openlp.plugins.obs_studio.lib.message_listener` module contains
the MessageListener class for the OBS Studio plugin.
"""
import logging
import threading
import time
import websocket

from openlp.core.common.registry import Registry
from openlp.plugins.obs_studio.lib.obs_studio_api import ObsStudioAPI

log = logging.getLogger(__name__)


class MessageListener():
    """
    This is the OBS Studio message listener that acts on events from the slide controller and
    passes the messages.
    """
    log.info('MessageListener loaded')

    def __init__(self, host: str, port: int, password: str):
        self.client = None
        self.is_connected = False
        self.is_active = False
        self.__host = host
        self.__port = port
        self.__password = password
        self._condition = threading.Condition()
        self._pending_message = None
        self._stopping = False
        self._worker = None
        self._retry_after = 0
        self.__setup()

    def __setup(self):
        """
        Setup the message listener.
        """
        # Messages are sent from core.ui.slidecontroller
        Registry().register_function('slidecontroller_slide_selected', self.slide_selected)

    def connect(self):
        """
        Connect to the OBS Studio WebSocket server.
        """
        try:
            self.client = ObsStudioAPI(self.__host, self.__port, self.__password)
            self.is_connected = True
            log.info("Connected successfully to OBS Studio.")
        except (OSError, websocket.WebSocketException, ValueError, KeyError, TypeError) as exception:
            self.client = None
            self.is_connected = False
            log.error("Failed to make a connection to OBS Studio: %s", exception)

    def slide_selected(self, message):
        """
        Handle a message when a slide is selected for the live output.

        :param message: The message to handle.
        """
        if not self.is_active or not message[1]:
            return
        slide = message[0]
        text = (f"type: {slide.name}, title: {slide.title}, slide: {message[2] + 1}, "
                f"notes: {slide.notes}")
        with self._condition:
            if self._stopping:
                return
            # Keep only the latest slide when the operator advances quickly.
            self._pending_message = text
            if self._worker is None:
                self._worker = threading.Thread(target=self._send_pending, daemon=True, name='OpenLP OBS sender')
                self._worker.start()
            self._condition.notify()

    def _send_pending(self):
        """Own the socket on one worker; never wait for OBS on the UI thread."""
        try:
            while True:
                with self._condition:
                    while not self._stopping:
                        delay = max(0, self._retry_after - time.monotonic())
                        if self._pending_message is not None and delay == 0:
                            break
                        self._condition.wait(delay if self._pending_message is not None else None)
                    if self._stopping:
                        return
                if not self.is_connected:
                    self.connect()
                if not self.is_connected:
                    self._retry_after = time.monotonic() + 15
                    continue
                with self._condition:
                    if self._stopping:
                        return
                    text = self._pending_message
                    self._pending_message = None
                try:
                    self.client.send_advanced_scene_switcher_message(text)
                except (OSError, websocket.WebSocketException) as exception:
                    log.error("Message could not be processed by OBS Studio: %s", exception)
                    self._disconnect()
                    self._retry_after = time.monotonic() + 15
        finally:
            self._disconnect()

    def _disconnect(self):
        if self.client is not None:
            try:
                self.client.disconnect()
            except (OSError, websocket.WebSocketException):
                log.debug('OBS socket was already closed', exc_info=True)
        self.client = None
        self.is_connected = False

    def finalise(self):
        """
        Finalise the message listener.
        """
        with self._condition:
            self._stopping = True
            self._pending_message = None
            self._condition.notify_all()
