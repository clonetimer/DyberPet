"""Optional real HTTP integration with the user's PPL Character Governance product.

Only executed by the dedicated Node 22 + PPL GitHub Actions job. It does
not bundle or modify PPL's source; it runs PPL from a separate local checkout.
"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from DyberPet.assistant.persona import PPLCharacterClient


@unittest.skipUnless(os.environ.get("PPL_INTEGRATION_HOME"),
                     "Requires independently checked-out PPL source")
class RealPPLCharacterTest(unittest.TestCase):
    def test_http_session_event_idempotency_and_sqlite_restart(self):
        home = Path(os.environ["PPL_INTEGRATION_HOME"]).resolve()
        node = shutil.which("node")
        if node is None:
            self.fail("Node >=22 required by PPL")
        service = home / "product" / "character-governance" / "bin" / "server.mjs"
        self.assertTrue(service.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            base_url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            env.update({"PPL_HOST": "127.0.0.1", "PPL_PORT": str(port),
                        "PPL_DB": str(Path(tmp) / "character.sqlite")})
            def boot():
                proc = subprocess.Popen(
                    [node, str(service)], cwd=str(home), env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                client = PPLCharacterClient(base_url)
                for _ in range(80):
                    if proc.poll() is not None:
                        self.fail("PPL server process exited before health became ready")
                    try:
                        if client.health().get("ok"):
                            return proc, client
                    except Exception:
                        time.sleep(0.15)
                proc.terminate()
                proc.wait(timeout=10)
                self.fail("PPL service did not become ready")
            proc, client = boot()
            try:
                initial = client.state("Synthetic-Q-Pet")
                self.assertIn("relationship", initial)
                old_trust = initial["relationship"]["trust"]
                state = client.event("Synthetic-Q-Pet", "COMFORT",
                                     "synthetic-event-1")
                self.assertGreater(state["relationship"]["trust"], old_trust)
                duplicate = client.event("Synthetic-Q-Pet", "COMFORT",
                                          "synthetic-event-1")
                self.assertEqual(
                    duplicate["relationship"]["trust"],
                    state["relationship"]["trust"])
            finally:
                proc.terminate()
                proc.wait(timeout=10)
            proc2, client2 = boot()
            try:
                recovered = client2.state("Synthetic-Q-Pet")
                self.assertEqual(
                    recovered["relationship"]["trust"],
                    state["relationship"]["trust"])
            finally:
                proc2.terminate()
                proc2.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
