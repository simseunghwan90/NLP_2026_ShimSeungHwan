"""Terminal handoff framing, validation and single session ownership."""

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from f1_session_control import ControlServer, validate_request  # noqa: E402


class SessionControlTest(unittest.TestCase):
    def test_rejects_invalid_motion_requests(self):
        for fields in (
            {"duration": -1},
            {"speed_cap": 0},
            {"speed_cap": float("nan")},
            {"duration": True},
            {"action": "arm"},
            {"extra": 1},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                validate_request(dict(dict(action="drive", duration=0, speed_cap=6), **fields))

    def test_combined_start_stop_frames_and_reply(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ControlServer(Path(folder) / "control.sock")
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(1)
                    client.connect(str(server.path))
                    client.sendall(b'{"action":"drive","duration":0,"speed_cap":6}\n{"action":"stop"}\n')
                    self.assertEqual(server.wait_for_drive(lambda: None)["speed_cap"], 6)
                    with socket.socket(socket.AF_UNIX) as duplicate, self.assertRaises(ConnectionRefusedError):
                        duplicate.connect(str(server.path))
                    self.assertTrue(server.stop_requested())
                    server.send("done", status="PASS")
                    self.assertEqual(json.loads(client.recv(4096))["status"], "PASS")
            finally:
                server.close()
            self.assertFalse(server.path.exists())

    def test_lost_client_requests_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ControlServer(Path(folder) / "control.sock")
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(str(server.path))
                    client.sendall(b'{"action":"drive","duration":0,"speed_cap":6}\n')
                    server.wait_for_drive(lambda: None)
                self.assertTrue(server.stop_requested())
            finally:
                server.close()

    def test_duplicate_server_does_not_unlink_active_socket(self):
        with tempfile.TemporaryDirectory() as folder:
            server = ControlServer(Path(folder) / "control.sock")
            try:
                with self.assertRaises(BlockingIOError):
                    ControlServer(server.path)
                self.assertTrue(server.path.exists())
            finally:
                server.close()


if __name__ == "__main__":
    unittest.main()
