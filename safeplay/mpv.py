from __future__ import annotations

import json
import os
import socket
import threading


class MpvError(RuntimeError):
    pass


class MpvCommandError(MpvError):
    pass


def syncplay_pipes():
    """Find Syncplay's mpv IPC endpoints without changing the player session."""
    if os.name != "nt":
        return []
    try:
        return ["\\\\.\\pipe\\" + name for name in os.listdir(r"\\.\pipe")
                if name.startswith("syncplay-mpv-")]
    except OSError:
        return []


class MpvClient:
    """Synchronous JSON IPC client. Call from a worker thread, not the GUI thread."""

    def __init__(self, endpoint=r"\\.\pipe\safeplay-mpv", transport=None):
        self.endpoint = endpoint
        self.transport = transport
        self._next_id = 0
        self._lock = threading.RLock()
        self.events: list[dict] = []

    def connect(self):
        if self.transport is not None:
            return
        try:
            if os.name == "nt":
                if not self.endpoint.startswith("\\\\.\\pipe\\"):
                    raise MpvError("IPC endpoint must be a Windows named pipe")
                self.transport = open(self.endpoint, "r+b", buffering=0)
            else:
                sock = socket.socket(socket.AF_UNIX)
                sock.settimeout(4)
                sock.connect(self.endpoint)
                self.transport = sock
        except (OSError, ValueError) as exc:
            raise MpvError(f"Cannot connect to mpv: {exc}") from exc

    def close(self):
        if self.transport:
            try:
                self.transport.close()
            finally:
                self.transport = None

    def _write(self, data: bytes):
        if isinstance(self.transport, socket.socket):
            self.transport.sendall(data)
        else:
            self.transport.write(data)

    def _readline(self):
        data = bytearray()
        while len(data) < 1024 * 1024:
            ch = self.transport.recv(1) if isinstance(self.transport, socket.socket) else self.transport.read(1)
            if not ch:
                raise MpvError("mpv IPC disconnected")
            if ch == b"\n":
                try:
                    return json.loads(data)
                except ValueError as exc:
                    raise MpvError("Invalid JSON from mpv") from exc
            data.extend(ch)
        raise MpvError("mpv IPC message exceeded limit")

    def command(self, *args):
        with self._lock:
            if self.transport is None:
                self.connect()
            self._next_id += 1
            request_id = self._next_id
            try:
                self._write((json.dumps({"command": list(args), "request_id": request_id}) + "\n").encode())
                while True:
                    response = self._readline()
                    if not isinstance(response, dict):
                        raise MpvError("Invalid mpv IPC response")
                    if response.get("request_id") != request_id:
                        if "event" in response:
                            self.events.append(response)
                        continue
                    if response.get("error") != "success":
                        raise MpvCommandError(f"mpv command failed: {response.get('error')}")
                    return response.get("data")
            except MpvCommandError:
                raise
            except (OSError, TimeoutError, BrokenPipeError, MpvError) as exc:
                self.close()
                raise MpvError(f"mpv IPC error: {exc}") from exc

    def property(self, name):
        return self.command("get_property", name)

    def snapshot(self):
        result = {}
        for prop in ("path", "time-pos", "duration", "pause"):
            try:
                result[prop] = self.property(prop)
            except MpvCommandError:
                result[prop] = None
        return result

    def seek(self, position: float):
        return self.command("seek", float(position), "absolute+exact")
