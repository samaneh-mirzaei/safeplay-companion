"""Windows named-pipe transport integration without requiring mpv."""
import ctypes
import json
import os
import threading

import pytest

from safeplay.mpv import MpvClient


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipes only")
def test_windows_named_pipe_roundtrip():
    kernel = ctypes.windll.kernel32
    kernel.CreateNamedPipeW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                        ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateNamedPipeW.restype = ctypes.c_void_p
    kernel.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    kernel.WriteFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                 ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    endpoint = rf"\\.\pipe\safeplay-test-{os.getpid()}"
    ready = threading.Event()
    errors = []

    def server():
        handle = kernel.CreateNamedPipeW(endpoint, 3, 0, 1, 4096, 4096, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            errors.append("CreateNamedPipeW failed")
            ready.set()
            return
        try:
            ready.set()
            if not kernel.ConnectNamedPipe(handle, None):
                errors.append("ConnectNamedPipe failed")
                return
            buffer = ctypes.create_string_buffer(4096)
            count = ctypes.c_uint32()
            if not kernel.ReadFile(handle, buffer, 4096, ctypes.byref(count), None):
                errors.append("ReadFile failed")
                return
            request = json.loads(buffer.raw[:count.value])
            response = (json.dumps({"request_id": request["request_id"],
                                    "error": "success", "data": "movie.mkv"}) + "\n").encode()
            written = ctypes.c_uint32()
            if not kernel.WriteFile(handle, ctypes.c_char_p(response), len(response),
                                    ctypes.byref(written), None):
                errors.append("WriteFile failed")
        finally:
            kernel.CloseHandle(handle)

    thread = threading.Thread(target=server)
    thread.start()
    assert ready.wait(2)
    client = MpvClient(endpoint)
    try:
        assert client.property("path") == "movie.mkv"
    finally:
        client.close()
    thread.join(timeout=2)
    assert not errors
