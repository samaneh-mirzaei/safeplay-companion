import json
import socket
import threading

import pytest

from safeplay.mpv import MpvClient, MpvError


def test_json_ipc_with_mock_server():
    client_sock, server_sock = socket.socketpair()
    seen = []

    def server():
        data = bytearray()
        try:
            while len(seen) < 2:
                chunk = server_sock.recv(1)
                if chunk == b"\n":
                    request = json.loads(data)
                    seen.append(request["command"])
                    if len(seen) == 1:
                        server_sock.sendall(b'{"event":"property-change","name":"pause","data":false}\n')
                    response = {"request_id": request["request_id"], "error": "success",
                                "data": "video.mkv" if len(seen) == 1 else None}
                    server_sock.sendall((json.dumps(response) + "\n").encode())
                    data.clear()
                else:
                    data.extend(chunk)
        finally:
            server_sock.close()

    thread = threading.Thread(target=server); thread.start()
    client = MpvClient(transport=client_sock)
    assert client.property("path") == "video.mkv"
    client.seek(42)
    assert seen == [["get_property", "path"], ["seek", 42.0, "absolute+exact"]]
    assert client.events[0]["event"] == "property-change"
    client.close(); thread.join(timeout=2)


def test_disconnect_closes_transport():
    client_sock, server_sock = socket.socketpair()
    server_sock.close()
    client = MpvClient(transport=client_sock)
    with pytest.raises(MpvError):
        client.property("path")
    assert client.transport is None
