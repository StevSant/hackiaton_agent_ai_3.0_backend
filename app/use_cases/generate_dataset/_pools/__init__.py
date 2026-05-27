"""Seed pools consumed by the synthetic-dataset generator.

Each constant is loaded from a JSON file under ``data/config/`` — edit the
JSON, not Python, to change a pool. Pools are exposed via package-level
re-exports so consumers import from ``_pools``, not the individual modules.
"""

from app.use_cases.generate_dataset._pools.apellidos import APELLIDOS
from app.use_cases.generate_dataset._pools.code_provider_patterns import (
    CODE_PROVIDER_PATTERNS,
)
from app.use_cases.generate_dataset._pools.marcas_vehiculo import MARCAS_VEHICULO
from app.use_cases.generate_dataset._pools.modelos_vehiculo import MODELOS_VEHICULO
from app.use_cases.generate_dataset._pools.nombres_femeninos import NOMBRES_FEMENINOS
from app.use_cases.generate_dataset._pools.nombres_masculinos import NOMBRES_MASCULINOS
from app.use_cases.generate_dataset._pools.proveedor_prefijos import PROVEEDOR_PREFIJOS
from app.use_cases.generate_dataset._pools.proveedor_qualifiers import (
    PROVEEDOR_QUALIFIERS,
)
from app.use_cases.generate_dataset._pools.proveedores_default import (
    PROVEEDORES_DEFAULT,
)
from app.use_cases.generate_dataset._pools.proveedores_generales import (
    PROVEEDORES_GENERALES,
)
from app.use_cases.generate_dataset._pools.proveedores_hogar import (
    PROVEEDORES_HOGAR,
)
from app.use_cases.generate_dataset._pools.proveedores_salud import (
    PROVEEDORES_SALUD,
)
from app.use_cases.generate_dataset._pools.ramos_vehiculo import RAMOS_VEHICULO
from app.use_cases.generate_dataset._pools.sucursales import SUCURSALES

__all__ = [
    "APELLIDOS",
    "CODE_PROVIDER_PATTERNS",
    "MARCAS_VEHICULO",
    "MODELOS_VEHICULO",
    "NOMBRES_FEMENINOS",
    "NOMBRES_MASCULINOS",
    "PROVEEDOR_PREFIJOS",
    "PROVEEDOR_QUALIFIERS",
    "PROVEEDORES_DEFAULT",
    "PROVEEDORES_GENERALES",
    "PROVEEDORES_HOGAR",
    "PROVEEDORES_SALUD",
    "RAMOS_VEHICULO",
    "SUCURSALES",
]
