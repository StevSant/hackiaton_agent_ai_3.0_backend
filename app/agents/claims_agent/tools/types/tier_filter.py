from typing import Literal

TierFilter = Literal["rojo", "amarillo", "amarillo+rojo", "all"]
"""Tier filter used by query and aggregate tools.

Default is `amarillo+rojo` — the analyst-focused view. `all` includes verde
(used for broad pattern-discovery questions like Q10).
"""
