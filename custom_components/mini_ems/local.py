"""Local (cloud-free) TCP Server mode for Mini EMS / Absaar / Donnergy inverters."""
from __future__ import annotations

import asyncio
import logging
import re
import struct
from urllib.parse import urlparse

import aiohttp
import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MAGIC = bytes.fromhex("ea91")
DATA_LEN = 164
LOGIN_LEN = 19
QUERY_SUFFIX = bytes.fromhex("000000000000000811040000003c8bf2")
MAX_FRAME_LEN = 1024
OFFLINE_GRACE = 90

# Offsets in 164-byte frame
FIELDS = {
    44: ("pv1_voltage", 10),
    46: ("pv2_voltage", 10),
    52: ("ac_voltage", 10),
    58: ("pv1_current", 10),
    60: ("pv2_current", 10),
    66: ("total_energy", 10),
    68: ("ac_frequency", 100),
    78: ("pv1_power", 1),
    82: ("pv2_power", 1),
    90: ("ac_power", 1),
}


class MiniEmsLocalHub:
    """TCP server for direct local connection from the inverter's Wi-Fi stick."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        port: int,
        serial: str,
        poll_delay: int = 5,
        datalogger_url: str = "",
        datalogger_username: str = "",
        datalogger_password: str = "",
        listener_ip: str = "",
        ip_check_interval: int = 300,
    ) -> None:
        """Initialize the local hub."""
        self._hass = hass
        self._entry_id = entry_id
        self._port = port
        self.serial = (serial or "").strip()
        self._poll_delay = max(int(poll_delay), 1)

        url = (datalogger_url or "").strip().rstrip("/")
        if url and not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        self._datalogger_url = url
        self._datalogger_username = datalogger_username
        self._datalogger_password = datalogger_password
        self._listener_ip = (listener_ip or "").strip()
        self._ip_check_interval = max(int(ip_check_interval), 30)

        self.data: dict[str, float] = {}
        self.online = False
        self.last_seen = None

        self._server: asyncio.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._offline_timer = None
        self.on_serial = None
        self._reported_serial = ""

    @property
    def signal(self) -> str:
        """Dispatcher signal name for entity updates."""
        return f"{DOMAIN}_{self._entry_id}_local_update"

    async def async_start(self) -> None:
        """Start the local TCP server."""
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self._port
        )
        _LOGGER.info("Mini EMS / Absaar local listener active on port %s", self._port)

    async def async_stop(self) -> None:
        """Stop local TCP server."""
        self._cancel_offline_timer()
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        _LOGGER.info("Inverter datalogger connected from %s", peer)

        if self._writer is not None:
            self._writer.close()
        self._writer = writer

        buf = b""
        data_timeout = max(self._poll_delay + 30, 60)
        timeout = 15
        proactive_sent = False

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(reader.read(1024), timeout=timeout)
                except asyncio.TimeoutError:
                    if not proactive_sent:
                        proactive_sent = True
                        timeout = data_timeout
                        _LOGGER.debug("Querying inverter proactively at %s", peer)
                        writer.write(self._build_query())
                        await writer.drain()
                        continue
                    _LOGGER.debug("Datalogger %s timed out", peer)
                    break

                if not chunk:
                    _LOGGER.debug("Datalogger %s disconnected", peer)
                    break

                timeout = data_timeout
                buf += chunk
                buf = await self._process_buffer(buf, writer)
        except (ConnectionResetError, OSError) as err:
            _LOGGER.debug("Local connection error from %s: %s", peer, err)
        finally:
            if self._writer is writer:
                self._writer = None
                self._schedule_offline()
            writer.close()

    async def _process_buffer(self, buf: bytes, writer: asyncio.StreamWriter) -> bytes:
        while len(buf) >= 6:
            if buf[:2] != MAGIC:
                idx = buf.find(MAGIC)
                buf = buf[idx:] if idx != -1 else b""
                continue

            frame_len = struct.unpack_from(">H", buf, 4)[0] + 6
            if frame_len > MAX_FRAME_LEN:
                buf = buf[2:]
                continue
            if len(buf) < frame_len:
                break

            frame = buf[:frame_len]
            buf = buf[frame_len:]
            cmd = frame[6] if len(frame) > 6 else 0
            subcmd = frame[7] if len(frame) > 7 else 0

            # Login frame from stick logger
            if cmd == 0x01 and subcmd == 0x01 and len(frame) == LOGIN_LEN:
                reported = frame[8:18].decode("ascii", errors="replace").rstrip("\x00")
                self._learn_serial(reported)
                _LOGGER.info("Login from serial %s, querying measurements...", self.serial)
                writer.write(self._build_query())
                await writer.drain()

            # Data frame reply (164 bytes)
            elif cmd == 0x01 and subcmd == 0x02 and len(frame) == DATA_LEN:
                self._handle_data_frame(frame)
                await asyncio.sleep(self._poll_delay)
                writer.write(self._build_query())
                await writer.drain()

        return buf

    def _learn_serial(self, serial: str) -> None:
        if not serial:
            return
        self.serial = serial
        if serial != self._reported_serial:
            self._reported_serial = serial
            if self.on_serial is not None:
                self.on_serial(serial)

    def _handle_data_frame(self, frame: bytes) -> None:
        serial = frame[8:18].decode("ascii", errors="replace").rstrip("\x00")
        self._learn_serial(serial)

        for offset, (key, divisor) in FIELDS.items():
            self.data[key] = struct.unpack_from(">H", frame, offset)[0] / divisor

        self.data["pv_total_power"] = self.data.get("pv1_power", 0) + self.data.get("pv2_power", 0)
        self.last_seen = dt_util.utcnow()
        self._cancel_offline_timer()
        self._set_online(True)
        self._notify()

    def _build_query(self) -> bytes:
        serial_bytes = self.serial.encode("ascii")[:10].ljust(10, b"\x00")
        return (
            MAGIC
            + b"\x00\x01"
            + b"\x00\x1c"
            + b"\x01\x02"
            + serial_bytes
            + QUERY_SUFFIX
        )

    @callback
    def _set_online(self, online: bool) -> None:
        if self.online != online:
            self.online = online
            self._notify()

    @callback
    def _schedule_offline(self) -> None:
        self._cancel_offline_timer()
        self._offline_timer = self._hass.loop.call_later(
            OFFLINE_GRACE, self._set_online, False
        )

    @callback
    def _cancel_offline_timer(self) -> None:
        if self._offline_timer is not None:
            self._offline_timer.cancel()
            self._offline_timer = None

    def _notify(self) -> None:
        async_dispatcher_send(self._hass, self.signal)
