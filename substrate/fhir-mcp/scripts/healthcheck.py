"""Docker HEALTHCHECK probe: is the server answering /healthz on its own port.

Not a test, and not run by pytest, same reasoning as scripts/smoke_test.py:
this needs the real process up, which a unit test does not have.
"""

from __future__ import annotations

import os
import sys
import urllib.request

port = os.environ.get("FHIR_MCP_PORT", "3001")
url = f"http://127.0.0.1:{port}/healthz"

try:
    with urllib.request.urlopen(url, timeout=2) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
