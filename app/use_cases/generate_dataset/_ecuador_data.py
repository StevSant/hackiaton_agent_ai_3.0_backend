"""Pools of Ecuadorian names, surnames and business names for the synthetic generator.

Used by:
- ``_claim_builder.py`` to give every claim a real-looking asegurado name (replaces
  the old ``"Asegurado <hash>"`` placeholder).
- ``_samples.py`` via the same ``_ecuador_name`` helper.

Lists are intentionally short and curated. Deterministic indexing in the
generators picks one entry per claim seed, so duplicates are fine — the goal is
*plausible*, not *unique*.

Sources: census-frequent first names and surnames in Ecuador (INEC public stats
+ widely-published frequency lists). No real PII; these are pool-level only.
"""

from __future__ import annotations

NOMBRES_MASCULINOS: list[str] = [
    "Carlos", "Luis", "José", "Juan", "Marco", "Diego", "Andrés", "Pablo",
    "Manuel", "Jorge", "Fernando", "Alejandro", "Daniel", "Roberto", "David",
    "Esteban", "Miguel", "Iván", "Patricio", "Cristian", "Mauricio", "Ricardo",
    "Javier", "Eduardo", "Víctor", "Hugo", "Santiago", "Sebastián", "Felipe",
    "Ramiro", "Edison", "Walter", "Bryan", "Kevin", "Alex", "Marcelo",
    "Hernán", "Vinicio", "Wilmer", "Galo",
]

NOMBRES_FEMENINOS: list[str] = [
    "María", "Ana", "Rosa", "Carmen", "Lucía", "Diana", "Verónica", "Patricia",
    "Mónica", "Andrea", "Gabriela", "Paola", "Cecilia", "Lorena", "Karina",
    "Mercedes", "Elena", "Pilar", "Tatiana", "Sandra", "Daniela", "Valeria",
    "Camila", "Sofía", "Adriana", "Johanna", "Karla", "Estefanía", "Jessica",
    "Erika", "Belén", "Mishell", "Doménica", "Anahí", "Génesis", "Nicole",
    "Pamela", "Silvia", "Ximena", "Yolanda",
]

APELLIDOS: list[str] = [
    "Pérez", "García", "López", "Mendoza", "Rodríguez", "Sánchez", "Ramírez",
    "Torres", "Flores", "Vega", "Castro", "Rivera", "Jiménez", "Herrera",
    "Vargas", "Romero", "Gómez", "Reyes", "Ortiz", "Cruz", "Moreno", "Aguilar",
    "Cabrera", "Morales", "Cevallos", "Salazar", "Cárdenas", "Espinoza",
    "Carrillo", "Suárez", "Andrade", "Mora", "Bravo", "Toro", "Paredes",
    "Velasco", "Zambrano", "Sandoval", "Vásquez", "Naranjo", "Cedeño",
    "Bermeo", "Quiroz", "Mosquera", "Solórzano", "Garcés", "Pacheco",
    "Tapia", "Cárdenas", "Aguirre",
]

# Business name building blocks for plausible Ecuadorian providers (talleres,
# carrocerías, repuestos, clínicas, centros médicos).  Combine prefix + place /
# qualifier deterministically.
PROVEEDOR_PREFIJOS: list[str] = [
    "Taller Mecánico",
    "Taller Automotriz",
    "Carrocerías",
    "Repuestos",
    "Mega Repuestos",
    "Auto Servicio",
    "Servicios Automotrices",
    "Centro Automotriz",
    "Mecánica Integral",
    "Reparaciones",
    "Multitalleres",
    "Centro Técnico",
    "Tecnomotor",
    "Automotores",
    "AutoRepair",
    "Servicar",
    "Clínica",
    "Centro Médico",
    "Policlínico",
]

PROVEEDOR_QUALIFIERS: list[str] = [
    "del Pacífico", "del Valle", "Los Andes", "del Austro", "Costa Norte",
    "Manabí", "Sierra Sur", "Sur", "Norte", "Centro", "La Aurora",
    "La Alborada", "Tarqui", "El Inca", "La Carolina", "Iñaquito",
    "Cumbayá", "Tumbaco", "Samborondón", "Daule", "Eloy Alfaro",
    "Mariscal", "San Marino", "La Mariscal", "Calderón", "Río Verde",
    "El Recreo", "Chillogallo", "Quitumbe", "Salinas",
]
