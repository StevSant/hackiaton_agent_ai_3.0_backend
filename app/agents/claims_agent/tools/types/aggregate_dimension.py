from typing import Literal

AggregateDimension = Literal["proveedor", "ramo", "ciudad", "asegurado"]
"""Dimensions the agent can group claims by — matches the 12 NL questions in §2.6.

- `proveedor` → Q3 (which providers concentrate alerts)
- `ramo` → Q4 (which ramos have higher suspicious %)
- `ciudad` → Q5 (which cities have alert concentration)
- `asegurado` → Q6 (which insured have highest claim frequency)
"""
