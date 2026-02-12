from __future__ import annotations

import os

# Keep test runs deterministic and independent of external API/network state.
os.environ.setdefault("DR_USE_MOCK_SOURCES", "true")
