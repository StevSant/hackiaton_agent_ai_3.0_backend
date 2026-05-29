#!/usr/bin/env python3
"""Generate uploadable PDF document packages for demo cases SIN-DEMO-007, 009, 012.

Output: data/casos_demo/sample_documents/<claim_id>/*.pdf

Each package contains 5-7 PDFs named so ``sync_claim_document._FILENAME_TIPO_HINTS``
can infer the tipo from the filename keyword.

Usage::

    uv run python scripts/generate_demo_case_docs.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# Progress output uses ✓ — force UTF-8 so it doesn't crash on Windows cp1252.
sys.stdout.reconfigure(encoding="utf-8")

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
JSON_DIR = ROOT / "data" / "casos_demo" / "json"
OUTPUT_ROOT = ROOT / "data" / "casos_demo" / "sample_documents"

# ---------------------------------------------------------------------------
# Shared style helpers (adapted from generate_sample_claim_pdfs.py)
# ---------------------------------------------------------------------------


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=10,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#334155"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "alert": ParagraphStyle(
            "Alert",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#b91c1c"),
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#475569"),
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_LEFT,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#94a3b8"),
            alignment=TA_CENTER,
        ),
    }


def _header_block(
    story: list,
    styles: dict[str, ParagraphStyle],
    title: str,
    issuer: str,
) -> None:
    story.append(Paragraph(title, styles["title"]))
    story.append(Paragraph(issuer, styles["subtitle"]))
    story.append(Spacer(1, 0.15 * cm))


def _key_value_table(rows: list[tuple[str, str]]) -> Table:
    table = Table(rows, colWidths=[5.2 * cm, 10.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ]
        )
    )
    return table


def _footer(
    story: list,
    styles: dict[str, ParagraphStyle],
    doc_code: str,
    claim_id: str,
) -> None:
    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            f"Documento de muestra · Aseguradora del Sur · {doc_code} · "
            f"Siniestro {claim_id} · Generado {date.today():%d/%m/%Y}",
            styles["footer"],
        )
    )


def _write_pdf(path: Path, builder, *, claim: dict, styles: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.5 * cm,
        title=path.stem,
    )
    story: list = []
    builder(story, styles, claim)
    doc.build(story)


# ---------------------------------------------------------------------------
# Generic builders (reusable across cases)
# ---------------------------------------------------------------------------


def _build_cedula(story: list, styles: dict, claim: dict) -> None:
    _header_block(story, styles, "CÉDULA DE IDENTIDAD — COPIA", "Registro Civil del Ecuador")
    story.append(
        _key_value_table(
            [
                ("Nombres y apellidos", claim["asegurado"]),
                ("N.º cédula", claim.get("cedula", "—")),
                ("Nacionalidad", "Ecuatoriana"),
                ("Estado civil", claim.get("estado_civil", "Soltero/a")),
                ("Domicilio", claim["ciudad"]),
                ("Fecha de expedición", claim.get("cedula_expedicion", "01/01/2020")),
            ]
        )
    )
    _footer(story, styles, "DOC-CEDULA", claim["id"])


def _build_matricula(story: list, styles: dict, claim: dict) -> None:
    _header_block(story, styles, "MATRÍCULA VEHICULAR", "Agencia Nacional de Tránsito — ANT")
    v = claim["vehiculo"]
    story.append(
        _key_value_table(
            [
                ("Placa", v["placa"]),
                ("Marca / Modelo", f"{v['marca']} {v['modelo']}"),
                ("Año", str(v["anio"])),
                ("Color", claim.get("vehiculo_color", "Gris metalizado")),
                ("Clase", "SUV / Camioneta"),
                ("Chasis", v["chasis"]),
                ("Propietario", claim["asegurado"]),
                ("Identificación", claim.get("cedula", "—")),
                ("Estado registral", "ACTIVO"),
            ]
        )
    )
    _footer(story, styles, "DOC-MATRICULA", claim["id"])


def _build_acta(story: list, styles: dict, claim: dict) -> None:
    _header_block(story, styles, "ACTA DE PRIMER RESPONDIENTE", "Policía Nacional del Ecuador")
    v = claim["vehiculo"]
    story.append(
        _key_value_table(
            [
                ("N.º acta", f"PN-{claim['ciudad'].upper()[:3]}-2026-{claim['id'][-3:]}001"),
                ("Fecha de levantamiento", claim["fecha_ocurrencia"]),
                ("Ciudad", claim["ciudad"]),
                ("Tipo de evento", claim.get("tipo_evento_policial", "Accidente de tránsito")),
                ("Placa reportada", v["placa"]),
                ("Denunciante / involucrado", claim["asegurado"]),
            ]
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            claim.get("narrativa_policial", claim["descripcion"][:400] + " [...]"),
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-ACTA-POLICIAL", claim["id"])


def _build_caratula_poliza(story: list, styles: dict, claim: dict) -> None:
    _header_block(story, styles, "CARÁTULA DE PÓLIZA", "Aseguradora del Sur S.A.")
    story.append(
        _key_value_table(
            [
                ("N.º póliza", claim["poliza"]),
                ("Contratante", claim["asegurado"]),
                ("Ramo", claim["ramo"]),
                ("Plan", "Integral Plus Vehículos"),
                ("Vigencia desde", claim["fecha_inicio_poliza"]),
                ("Vigencia hasta", claim["fecha_fin_poliza"]),
                ("Suma asegurada", f"${claim['suma_asegurada']:,.2f}"),
                ("Cobertura principal", claim["cobertura"]),
                ("Deducible aplicable", claim.get("deducible", "10% del valor asegurado")),
            ]
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    if claim.get("nota_caratula"):
        story.append(Paragraph(f"<b>Nota analítica:</b> {claim['nota_caratula']}", styles["body"]))
    _footer(story, styles, "DOC-CARATULA-POLIZA", claim["id"])


def _build_peritaje(story: list, styles: dict, claim: dict) -> None:
    _header_block(story, styles, "INFORME DE PERITAJE TÉCNICO", "Perito independiente — SUPBAN")
    v = claim["vehiculo"]
    story.append(
        _key_value_table(
            [
                ("Referencia", f"PER-{claim['id']}"),
                ("Fecha de inspección", claim.get("fecha_peritaje", claim["fecha_reporte"])),
                ("Vehículo", f"{v['marca']} {v['modelo']} {v['anio']} · {v['placa']}"),
                (
                    "Valor comercial referencial",
                    f"${claim.get('valor_peritaje', claim['suma_asegurada']):,.2f}",
                ),
                (
                    "Conclusión",
                    claim.get(
                        "conclusion_peritaje",
                        "Daños estructurales compatibles con siniestro declarado",
                    ),
                ),
                (
                    "Observaciones",
                    claim.get("obs_peritaje", "Sin observaciones adicionales"),
                ),
            ]
        )
    )
    _footer(story, styles, "DOC-PERITAJE", claim["id"])


def _build_denuncia(story: list, styles: dict, claim: dict) -> None:
    _header_block(story, styles, "DENUNCIA POR DELITO DE ROBO", "Fiscalía General del Estado")
    v = claim["vehiculo"]
    story.append(
        _key_value_table(
            [
                ("N.º expediente", f"FGED-2026-{claim['id'][-3:]}001"),
                ("Fecha de presentación", claim["fecha_reporte"]),
                ("Delito denunciado", "Robo de vehículo motorizado"),
                ("Denunciante", claim["asegurado"]),
                ("Cédula", claim.get("cedula", "—")),
                ("Bien sustraído", f"{v['marca']} {v['modelo']} {v['anio']}"),
                ("Placa", v["placa"]),
                ("Chasis", v["chasis"]),
                ("Fecha del hecho", claim["fecha_ocurrencia"]),
            ]
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    if claim.get("obs_denuncia"):
        obs = claim["obs_denuncia"]
        story.append(
            Paragraph(
                f"<b>Observación de control interno:</b> {obs}",
                styles["body"],
            )
        )
    _footer(story, styles, "DOC-DENUNCIA-FISCAL", claim["id"])


# ---------------------------------------------------------------------------
# Case-specific proforma builders
# ---------------------------------------------------------------------------


def _build_proforma_caso07(story: list, styles: dict, claim: dict) -> None:
    """Proforma with emission date BEFORE the event — visible inconsistency for RF-02 demo."""
    _header_block(
        story,
        styles,
        "PROFORMA DE REPUESTOS Y MANO DE OBRA",
        claim.get("proveedor", "Taller Automotriz Andes Motor"),
    )
    story.append(
        _key_value_table(
            [
                ("RUC proveedor", "0102345678001"),
                ("Referencia", "PRO-2026-AM-00741"),
                # Fecha 2 days BEFORE the siniestro (ocurrencia 20-04, proforma 18-04)
                ("Fecha de emisión", "18/04/2026"),
                (
                    "Vehículo",
                    (
                        f"{claim['vehiculo']['marca']} {claim['vehiculo']['modelo']}"
                        f" · {claim['vehiculo']['placa']}"
                    ),
                ),
                ("Concepto", "Puerta delantera derecha + espejo + guardafango"),
                ("Mano de obra", "$1 800.00"),
                ("Repuestos originales", "$7 400.00"),
                ("IVA 12%", "$1 104.00"),
                ("TOTAL", "$10 304.00"),
            ]
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            "<b>ALERTA — REQUIERE REVISIÓN:</b> La fecha de emisión de este documento "
            "(18/04/2026) es ANTERIOR a la fecha de ocurrencia del siniestro declarado "
            "(20/04/2026). Esta inconsistencia documental activa la señal RF-02 y requiere "
            "validación por la unidad antifraude antes de proceder con el pago.",
            styles["alert"],
        )
    )
    _footer(story, styles, "DOC-PROFORMA-INCONSISTENTE", claim["id"])


def _build_proforma_generic(story: list, styles: dict, claim: dict) -> None:
    """Standard proforma for cases without deliberate inconsistency."""
    _header_block(
        story,
        styles,
        "PROFORMA DE REPUESTOS Y MANO DE OBRA",
        claim.get("proveedor", "Taller Autorizado"),
    )
    story.append(
        _key_value_table(
            [
                ("RUC proveedor", claim.get("proveedor_ruc", "0190000000001")),
                ("Referencia", f"PRO-2026-{claim['id'][-3:]}"),
                ("Fecha de emisión", claim["fecha_reporte"]),
                (
                    "Vehículo",
                    (
                        f"{claim['vehiculo']['marca']} {claim['vehiculo']['modelo']}"
                        f" · {claim['vehiculo']['placa']}"
                    ),
                ),
                ("Concepto", "Reparación de daños + mano de obra"),
                ("Subtotal", f"${claim['monto_reclamado'] * 0.88:,.2f}"),
                ("IVA 12%", f"${claim['monto_reclamado'] * 0.12:,.2f}"),
                ("TOTAL", f"${claim['monto_reclamado']:,.2f}"),
            ]
        )
    )
    _footer(story, styles, "DOC-PROFORMA", claim["id"])


# ---------------------------------------------------------------------------
# Declarative builder factory (non-vehicle ramos: salud / vida / hogar)
# ---------------------------------------------------------------------------


def make_doc(title, issuer, rows_fn, *, body_fn=None, alert_fn=None, doc_code="DOC"):
    """Return a builder(story, styles, claim) from declarative content.

    issuer may be a string or a callable(claim). rows_fn/body_fn/alert_fn take
    the merged claim dict; body/alert paragraphs are skipped when they return
    a falsy value.
    """

    def builder(story: list, styles: dict, claim: dict) -> None:
        iss = issuer(claim) if callable(issuer) else issuer
        _header_block(story, styles, title, iss)
        story.append(_key_value_table(rows_fn(claim)))
        if body_fn is not None and (txt := body_fn(claim)):
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(txt, styles["body"]))
        if alert_fn is not None and (atxt := alert_fn(claim)):
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph(atxt, styles["alert"]))
        _footer(story, styles, doc_code, claim["id"])

    return builder


def _prov(claim: dict) -> str:
    return claim.get("proveedor") or "Aseguradora del Sur S.A."


_caratula_generica = make_doc(
    "CARÁTULA DE PÓLIZA",
    "Aseguradora del Sur S.A.",
    lambda c: [
        ("N.º póliza", c["poliza"]),
        ("Contratante", c["asegurado"]),
        ("Ramo", c["ramo"]),
        ("Vigencia desde", c["fecha_inicio_poliza"]),
        ("Vigencia hasta", c["fecha_fin_poliza"]),
        ("Suma asegurada", f"${c['suma_asegurada']:,.2f}"),
        ("Cobertura principal", c["cobertura"]),
    ],
    body_fn=lambda c: (f"<b>Nota analítica:</b> {c['nota_caratula']}" if c.get("nota_caratula") else None),
    doc_code="DOC-CARATULA-POLIZA",
)

# ── Salud / Accidentes Personales ──────────────────────────────────────────
_historia_clinica = make_doc(
    "HISTORIA CLÍNICA", _prov,
    lambda c: [
        ("Paciente", c["asegurado"]),
        ("N.º cédula", c.get("cedula", "—")),
        ("Establecimiento", _prov(c)),
        ("Fecha de atención", c["fecha_ocurrencia"]),
        ("Diagnóstico", c.get("diagnostico", "Cuadro clínico agudo")),
        ("Médico tratante", c.get("medico", "Médico de turno")),
    ],
    body_fn=lambda c: c.get("detalle_clinico"),
    doc_code="DOC-HISTORIA-CLINICA",
)

_factura_medica = make_doc(
    "FACTURA — SERVICIOS MÉDICOS", _prov,
    lambda c: [
        ("RUC emisor", c.get("proveedor_ruc", "1790012345001")),
        ("N.º factura", f"001-002-{c['id'][-6:]}"),
        ("Fecha de emisión", c["fecha_reporte"]),
        ("Paciente", c["asegurado"]),
        ("Concepto", c.get("concepto_factura", "Atención médica, exámenes y medicación")),
        ("Subtotal (servicios de salud, IVA 0%)", f"${c['monto_reclamado']:,.2f}"),
        ("TOTAL", f"${c['monto_reclamado']:,.2f}"),
    ],
    doc_code="DOC-FACTURA-MEDICA",
)

_informe_medico = make_doc(
    "INFORME MÉDICO", _prov,
    lambda c: [
        ("Paciente", c["asegurado"]),
        ("Fecha de atención", c["fecha_ocurrencia"]),
        ("Diagnóstico", c.get("diagnostico", "Cuadro clínico agudo")),
        ("Pronóstico", c.get("pronostico", "Favorable con tratamiento")),
        ("Médico responsable", c.get("medico", "Médico de turno")),
    ],
    body_fn=lambda c: c.get("detalle_clinico"),
    doc_code="DOC-INFORME-MEDICO",
)

_epicrisis = make_doc(
    "EPICRISIS / RESUMEN DE EGRESO", _prov,
    lambda c: [
        ("Paciente", c["asegurado"]),
        ("Fecha de ingreso", c["fecha_ocurrencia"]),
        ("Diagnóstico de egreso", c.get("diagnostico", "Resuelto")),
        ("Procedimiento", c.get("procedimiento", "Manejo clínico")),
        ("Condición al alta", c.get("condicion_alta", "Estable")),
    ],
    doc_code="DOC-EPICRISIS",
)

_certificado_incapacidad = make_doc(
    "CERTIFICADO DE INCAPACIDAD TEMPORAL", _prov,
    lambda c: [
        ("Paciente", c["asegurado"]),
        ("Fecha de emisión", c.get("fecha_doc_inconsistente", c["fecha_reporte"])),
        ("Fecha del accidente declarado", c["fecha_ocurrencia"]),
        ("Días de incapacidad", c.get("dias_incapacidad", "30")),
        ("Médico responsable", c.get("medico", "Médico ocupacional")),
    ],
    alert_fn=lambda c: c.get("alerta_doc"),
    doc_code="DOC-CERT-INCAPACIDAD",
)

_parte_accidente = make_doc(
    "PARTE DE ACCIDENTE LABORAL", "Riesgos del Trabajo — IESS",
    lambda c: [
        ("Trabajador", c["asegurado"]),
        ("Fecha del accidente", c["fecha_ocurrencia"]),
        ("Lugar", c["ciudad"]),
        ("Tipo de evento", c.get("tipo_evento", "Accidente de trabajo")),
    ],
    body_fn=lambda c: c["descripcion"][:380] + " [...]",
    doc_code="DOC-PARTE-ACCIDENTE",
)

# ── Vida ────────────────────────────────────────────────────────────────────
_certificado_defuncion = make_doc(
    "CERTIFICADO MÉDICO DE DEFUNCIÓN", "Ministerio de Salud Pública del Ecuador",
    lambda c: [
        ("Fallecido/a", c["asegurado"]),
        ("N.º cédula", c.get("cedula", "—")),
        ("Fecha de defunción", c["fecha_ocurrencia"]),
        ("Lugar", c["ciudad"]),
        ("Causa", c.get("causa_muerte", "Por determinar — ver informe")),
    ],
    doc_code="DOC-CERT-DEFUNCION",
)

_partida_defuncion = make_doc(
    "PARTIDA DE DEFUNCIÓN", "Registro Civil del Ecuador",
    lambda c: [
        ("N.º acta", f"RC-DEF-2026-{c['id'][-3:]}"),
        ("Fallecido/a", c["asegurado"]),
        ("Fecha de defunción", c["fecha_ocurrencia"]),
        ("Fecha de inscripción", c["fecha_reporte"]),
        ("Cantón", c["ciudad"]),
    ],
    doc_code="DOC-PARTIDA-DEFUNCION",
)

_designacion_beneficiario = make_doc(
    "DESIGNACIÓN DE BENEFICIARIO", "Aseguradora del Sur S.A.",
    lambda c: [
        ("N.º póliza", c["poliza"]),
        ("Asegurado", c["asegurado"]),
        ("Beneficiario designado", c.get("beneficiario", "—")),
        ("Parentesco / relación", c.get("parentesco", "—")),
        ("Porcentaje", c.get("porcentaje_beneficiario", "100%")),
    ],
    alert_fn=lambda c: c.get("alerta_doc"),
    doc_code="DOC-DESIGNACION-BENEFICIARIO",
)

_informe_forense = make_doc(
    "INFORME DE MEDICINA LEGAL", "Fiscalía General del Estado — Medicina Legal",
    lambda c: [
        ("Expediente", f"ML-2026-{c['id'][-3:]}"),
        ("Fallecido/a", c["asegurado"]),
        ("Fecha del hecho", c["fecha_ocurrencia"]),
        ("Manera de muerte", c.get("manera_muerte", "Accidental")),
    ],
    body_fn=lambda c: c["descripcion"][:380] + " [...]",
    doc_code="DOC-INFORME-FORENSE",
)

# ── Hogar / Incendio ────────────────────────────────────────────────────────
_informe_bomberos = make_doc(
    "INFORME DE INTERVENCIÓN", "Cuerpo de Bomberos del Ecuador",
    lambda c: [
        ("N.º parte", f"CB-2026-{c['id'][-3:]}"),
        ("Fecha de intervención", c["fecha_ocurrencia"]),
        ("Dirección", c["ciudad"]),
        ("Tipo de evento", c.get("tipo_evento", "Incendio estructural")),
        ("Origen probable", c.get("origen_fuego", "Cortocircuito eléctrico")),
    ],
    body_fn=lambda c: c["descripcion"][:380] + " [...]",
    doc_code="DOC-INFORME-BOMBEROS",
)

_inventario_bienes = make_doc(
    "INVENTARIO DE BIENES AFECTADOS", lambda c: c["asegurado"],
    lambda c: [
        ("Asegurado", c["asegurado"]),
        ("Domicilio", c["ciudad"]),
        ("Fecha del siniestro", c["fecha_ocurrencia"]),
        ("Bienes declarados", c.get("bienes", "Mobiliario, electrodomésticos y enseres")),
        ("Valor declarado", f"${c['monto_reclamado']:,.2f}"),
    ],
    doc_code="DOC-INVENTARIO-BIENES",
)

_factura_reparacion = make_doc(
    "FACTURA DE REPARACIÓN", _prov,
    lambda c: [
        ("RUC proveedor", c.get("proveedor_ruc", "1790098765001")),
        ("N.º factura", f"001-001-{c['id'][-6:]}"),
        ("Fecha de emisión", c["fecha_reporte"]),
        ("Cliente", c["asegurado"]),
        ("Concepto", c.get("concepto_factura", "Reparación de daños y materiales")),
        ("Subtotal", f"${c['monto_reclamado'] * 0.88:,.2f}"),
        ("IVA 12%", f"${c['monto_reclamado'] * 0.12:,.2f}"),
        ("TOTAL", f"${c['monto_reclamado']:,.2f}"),
    ],
    alert_fn=lambda c: c.get("alerta_doc"),
    doc_code="DOC-FACTURA-REPARACION",
)

_denuncia_sustraccion = make_doc(
    "DENUNCIA POR SUSTRACCIÓN DE BIENES", "Fiscalía General del Estado",
    lambda c: [
        ("N.º expediente", f"FGED-2026-{c['id'][-3:]}"),
        ("Fecha de presentación", c["fecha_reporte"]),
        ("Fecha del hecho", c["fecha_ocurrencia"]),
        ("Denunciante", c["asegurado"]),
        ("Bienes sustraídos", c.get("bienes", "Electrodomésticos y enseres")),
    ],
    body_fn=lambda c: c.get("obs_denuncia"),
    doc_code="DOC-DENUNCIA-SUSTRACCION",
)

_informe_pericial_danos = make_doc(
    "INFORME PERICIAL DE DAÑOS", "Perito independiente — SUPBAN",
    lambda c: [
        ("Referencia", f"PER-{c['id']}"),
        ("Fecha de inspección", c["fecha_reporte"]),
        ("Inmueble", c["ciudad"]),
        ("Valor de la pérdida", f"${c['monto_reclamado']:,.2f}"),
        ("Conclusión", c.get("conclusion_peritaje", "Daños compatibles con el siniestro declarado")),
    ],
    alert_fn=lambda c: c.get("alerta_doc"),
    doc_code="DOC-INFORME-PERICIAL",
)


# ---------------------------------------------------------------------------
# Per-case package definitions
# ---------------------------------------------------------------------------

CASES: dict[str, dict] = {
    "SIN-DEMO-007": {
        "extra": {
            "cedula": "0102345678",
            "estado_civil": "Casado",
            "cedula_expedicion": "15/03/2019",
            "vehiculo_color": "Blanco nacarado",
            "tipo_evento_policial": "Colisión contra objeto fijo",
            "narrativa_policial": (
                "El vehículo Kia Sportage placas AZD-3157 colisionó con poste "
                "de alumbrado en Av. Solano, El Ejido, Cuenca, el 20/04/2026 a "
                "las 14:30. Se constató daños en lateral derecho. El conductor "
                "presentó cédula y manifestó haber esquivado a un animal en la vía."
            ),
            "nota_caratula": (
                "El siniestro ocurre 95 días después del inicio de vigencia "
                "— fuera del borde crítico FS-01."
            ),
            "fecha_peritaje": "22/04/2026",
            "valor_peritaje": 18200.00,
            "conclusion_peritaje": (
                "Daños en lateral derecho compatibles con impacto lateral "
                "contra objeto fijo."
            ),
            "obs_peritaje": (
                "ALERTA: proforma del taller presenta fecha de emisión anterior "
                "a la ocurrencia del siniestro. Se recomienda revisión documental "
                "antes de autorizar pago."
            ),
        },
        "docs": [
            ("cedula_identidad.pdf", _build_cedula),
            ("matricula_vehiculo.pdf", _build_matricula),
            ("acta_policial.pdf", _build_acta),
            ("peritaje_tecnico.pdf", _build_peritaje),
            ("proforma_taller.pdf", _build_proforma_caso07),
            ("caratula_poliza.pdf", _build_caratula_poliza),
        ],
    },
    "SIN-DEMO-009": {
        "extra": {
            "cedula": "1803456789",
            "estado_civil": "Soltero",
            "cedula_expedicion": "22/07/2018",
            "vehiculo_color": "Negro brillante",
            "tipo_evento_policial": "Colisión frontal contra muro de contención",
            "narrativa_policial": (
                "El conductor reporta pérdida de frenos y colisión frontal a alta "
                "velocidad contra muro. El perito constata daños exclusivamente en "
                "lateral derecho y parte trasera, inconsistentes con la dinámica "
                "declarada. Se solicita revisión técnica ampliada."
            ),
            "deducible": "15% del valor asegurado",
            "nota_caratula": (
                "Siniestro ocurre 209 días desde el inicio de póliza — sin señal "
                "FS-01. RF-04 requiere NLP para detectar dinámica imposible."
            ),
            "fecha_peritaje": "29/04/2026",
            "valor_peritaje": 27500.00,
            "conclusion_peritaje": (
                "Daños estructurales en lateral derecho y zona trasera."
            ),
            "obs_peritaje": (
                "INCONSISTENCIA CRÍTICA: daños en lateral derecho y zona trasera, "
                "incompatibles con colisión frontal declarada. Se activa RF-04 "
                "(dinámica físicamente imposible). Registro de cámara contradice "
                "ubicación declarada del evento."
            ),
            "proveedor_ruc": "1801234567001",
        },
        "docs": [
            ("cedula_identidad.pdf", _build_cedula),
            ("matricula_vehiculo.pdf", _build_matricula),
            ("acta_policial.pdf", _build_acta),
            ("peritaje_tecnico.pdf", _build_peritaje),
            ("proforma_taller.pdf", _build_proforma_generic),
            ("caratula_poliza.pdf", _build_caratula_poliza),
            ("denuncia_fiscal.pdf", _build_denuncia),
        ],
    },
    "SIN-DEMO-012": {
        "extra": {
            "cedula": "1104567890",
            "estado_civil": "Casado",
            "cedula_expedicion": "05/09/2017",
            "vehiculo_color": "Azul oscuro",
            "tipo_evento_policial": "Robo de vehículo motorizado",
            "narrativa_policial": (
                "El asegurado denuncia la sustracción de su Ford Ranger placas "
                "LOJ-1148, ocurrida el 15/04/2026 a las 23:45 en calle Mercadillo, "
                "barrio La Tebaida, Loja. La denuncia es presentada el 25/04/2026, "
                "con una demora de 10 días respecto al hecho."
            ),
            "deducible": "10% del valor asegurado",
            "nota_caratula": (
                "Póliza contratada 5 días antes del siniestro (inicio 10/04/2026). "
                "RF-01 activo por cobertura PTxRB. FS-01 activo por borde crítico."
            ),
            "obs_denuncia": (
                "La denuncia fue presentada 10 días después de la ocurrencia. "
                "El plazo máximo en póliza para robo total es de 4 días (RF-06)."
            ),
            "fecha_peritaje": "26/04/2026",
            "valor_peritaje": 35000.00,
            "conclusion_peritaje": (
                "Vehículo no localizado. Valor comercial referencial establecido "
                "según peritaje de mercado."
            ),
            "obs_peritaje": (
                "Caso de robo total con RF-01 activo. Se recomienda revisión del "
                "expediente por demora en denuncia (RF-06) y cercanía al inicio de "
                "vigencia (FS-01). Monto es 97.7% de la suma asegurada (FS-14)."
            ),
            "proveedor_ruc": None,
        },
        "docs": [
            ("cedula_identidad.pdf", _build_cedula),
            ("matricula_vehiculo.pdf", _build_matricula),
            ("denuncia_fiscal.pdf", _build_denuncia),
            ("acta_policial.pdf", _build_acta),
            ("peritaje_tecnico.pdf", _build_peritaje),
            ("caratula_poliza.pdf", _build_caratula_poliza),
        ],
    },
    "SIN-DEMO-015": {
        "extra": {
            "cedula": "1307654321",
            "estado_civil": "Soltero",
            "cedula_expedicion": "10/06/2018",
            "vehiculo_color": "Gris oscuro",
            "tipo_evento_policial": "Robo de vehículo motorizado",
            "narrativa_policial": (
                "El asegurado denuncia la sustracción de su Nissan Frontier placas "
                "MNT-7756, ocurrida el 02/05/2026 a las 22:00 en calle 103, sector "
                "Puerto de Manta. La denuncia es presentada el 08/05/2026, con una "
                "demora de 6 días respecto al hecho (RF-06 activo)."
            ),
            "deducible": "10% del valor asegurado",
            "nota_caratula": (
                "Póliza contratada 8 días antes del siniestro (inicio 24/04/2026). "
                "RF-01 activo por cobertura PTxRB. FS-01 activo (+8 pts, ≤10 días). "
                "FS-14 activo (97.1% de suma asegurada)."
            ),
            "obs_denuncia": (
                "La denuncia fue presentada 6 días después de la ocurrencia. "
                "El plazo máximo en póliza para robo total es de 4 días (RF-06). "
                "Requiere revisión por la unidad antifraude."
            ),
            "fecha_peritaje": "09/05/2026",
            "valor_peritaje": 30000.00,
            "conclusion_peritaje": (
                "Vehículo no localizado al momento de la inspección. "
                "Valor comercial referencial según tablas de mercado vigentes."
            ),
            "obs_peritaje": (
                "Caso ROJO: RF-01 (PTxRB), RF-06 (demora denuncia 6 días), "
                "FS-01 (+8, póliza 8 días), FS-14 (ratio 97.1%), FS-08 (+4, 2 docs). "
                "Máxima densidad de señales auto-derivadas."
            ),
            "proveedor_ruc": None,
        },
        "docs": [
            ("cedula_identidad.pdf", _build_cedula),
            ("matricula_vehiculo.pdf", _build_matricula),
            ("denuncia_fiscal.pdf", _build_denuncia),
            ("acta_policial.pdf", _build_acta),
            ("peritaje_tecnico.pdf", _build_peritaje),
            ("caratula_poliza.pdf", _build_caratula_poliza),
        ],
    },
    "SIN-DEMO-018": {
        "extra": {
            "cedula": "0801234567",
            "estado_civil": "Casada",
            "cedula_expedicion": "20/03/2016",
            "vehiculo_color": "Blanco perla",
            "tipo_evento_policial": "Robo de vehículo motorizado",
            "narrativa_policial": (
                "La asegurada denuncia la sustracción de su Mitsubishi L200 placas "
                "ESM-3391, ocurrida el 18/05/2026 entre las 21:30 y las 23:00 en "
                "calle Los Álamos, sector Las Palmas, Esmeraldas. La denuncia ante "
                "Fiscalía fue presentada el 23/05/2026, con 5 días de demora (RF-06)."
            ),
            "deducible": "10% del valor asegurado",
            "nota_caratula": (
                "Póliza vigente desde 25/05/2025 hasta 25/05/2026. "
                "Siniestro ocurre 7 días antes del vencimiento — patrón de reclamo "
                "al cierre de vigencia. RF-01 activo por PTxRB. RF-06 activo (5 días). "
                "FS-14 activo (98.0% de suma asegurada)."
            ),
            "obs_denuncia": (
                "La denuncia fue presentada 5 días después de la ocurrencia. "
                "Plazo máximo en póliza: 4 días (RF-06). "
                "Siniestro a 7 días del vencimiento de la póliza — patrón atípico."
            ),
            "fecha_peritaje": "24/05/2026",
            "valor_peritaje": 27000.00,
            "conclusion_peritaje": (
                "Vehículo no localizado. Valor referencial según mercado Manabí-Esmeraldas."
            ),
            "obs_peritaje": (
                "Caso ROJO: RF-01 (PTxRB), RF-06 (demora 5 días), FS-14 (98.0%). "
                "Siniestro a 7 días del fin de vigencia — señal adicional de revisión. "
                "Se recomienda auditoría de expediente completo."
            ),
            "proveedor_ruc": None,
        },
        "docs": [
            ("cedula_identidad.pdf", _build_cedula),
            ("matricula_vehiculo.pdf", _build_matricula),
            ("denuncia_fiscal.pdf", _build_denuncia),
            ("acta_policial.pdf", _build_acta),
            ("peritaje_tecnico.pdf", _build_peritaje),
            ("caratula_poliza.pdf", _build_caratula_poliza),
        ],
    },
    "SIN-DEMO-020": {
        "extra": {
            "cedula": "0103456789",
            "estado_civil": "Casada",
            "cedula_expedicion": "12/08/2019",
            "vehiculo_color": "Plata metalizado",
            "tipo_evento_policial": "Robo de accesorios de vehículo",
            "narrativa_policial": (
                "La asegurada denuncia el robo de accesorios de su Volkswagen Tiguan "
                "placas AZU-8814, ocurrido el 05/05/2026 entre las 21:00 y las 23:00 "
                "en parqueadero público, calle Sangurima sector El Vergel, Cuenca. "
                "Se sustrajo la pantalla multimedia y parlantes. La denuncia fue "
                "presentada el 11/05/2026 — 6 días de demora (RF-06 activo)."
            ),
            "deducible": "10% del valor asegurado",
            "nota_caratula": (
                "Póliza vigente desde 20/01/2026. Cobertura: Robo Parcial. "
                "RF-01 NO aplica (cobertura no es PTxRB). RF-06 activo (demora 6 días). "
                "FS-08 activo (1 doc pendiente). Nivel AMARILLO por RF-06."
            ),
            "obs_denuncia": (
                "La denuncia fue presentada 6 días después de la ocurrencia. "
                "Plazo máximo en póliza para robo parcial: 4 días. "
                "RF-06 activo — piso AMARILLO garantizado."
            ),
            "fecha_peritaje": "12/05/2026",
            "valor_peritaje": 9700.00,
            "conclusion_peritaje": (
                "Daños confirmados en sistema multimedia y carrocería lateral derecha "
                "por rotura de vidrio. Accesorios sustraídos no recuperados."
            ),
            "obs_peritaje": (
                "Robo de accesorios confirmado. RF-06 por demora en denuncia (6 días). "
                "RF-01 no aplica — cobertura es Robo Parcial, no PTxRB. "
                "FS-08 activo por certificado multimedia pendiente."
            ),
            "proveedor_ruc": "0102345670001",
        },
        "docs": [
            ("cedula_identidad.pdf", _build_cedula),
            ("matricula_vehiculo.pdf", _build_matricula),
            ("denuncia_fiscal.pdf", _build_denuncia),
            ("acta_policial.pdf", _build_acta),
            ("peritaje_tecnico.pdf", _build_peritaje),
            ("caratula_poliza.pdf", _build_caratula_poliza),
        ],
    },
}


# ---------------------------------------------------------------------------
# Non-vehicle packages (salud / vida / hogar). Output lands under
# sample_documents/<ramo>/<claim_id>/, mirroring the json/<ramo>/ layout.
# ---------------------------------------------------------------------------

_CEDULAS = {
    "SIN-DEMO-021": "1712345678", "SIN-DEMO-022": "0923456781",
    "SIN-DEMO-023": "0103456782", "SIN-DEMO-024": "1804567893",
    "SIN-DEMO-025": "1305678904", "SIN-DEMO-026": "1106789015",
    "SIN-DEMO-027": "0917890126", "SIN-DEMO-028": "0608901237",
    "SIN-DEMO-029": "1309012348", "SIN-DEMO-030": "2300123459",
    "SIN-DEMO-031": "1710234560", "SIN-DEMO-032": "0701345671",
    "SIN-DEMO-033": "1802456782", "SIN-DEMO-034": "0913567893",
    "SIN-DEMO-035": "0104678904", "SIN-DEMO-036": "1715789015",
}

NONVEHIC_CASES: dict[str, dict] = {
    "SIN-DEMO-021": {"extra": {"diagnostico": "Gastroenteritis aguda",
        "detalle_clinico": "Paciente con cuadro de 24 horas de evolución; manejo ambulatorio con hidratación y antibiótico. Evolución favorable."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("historia_clinica.pdf", _historia_clinica), ("factura_medica.pdf", _factura_medica),
                 ("informe_medico.pdf", _informe_medico)]},
    "SIN-DEMO-022": {"extra": {"diagnostico": "Neumonía adquirida en la comunidad",
        "nota_caratula": "Reporte presentado 11 días después del egreso (FS-12). Faltan historia clínica y factura detallada (FS-08)."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("informe_medico.pdf", _informe_medico), ("epicrisis.pdf", _epicrisis)]},
    "SIN-DEMO-023": {"extra": {"diagnostico": "Colecistitis aguda — colecistectomía",
        "procedimiento": "Colecistectomía laparoscópica de urgencia",
        "nota_caratula": "Cirugía 1 día después del inicio de vigencia (20/04) → RF-05 piso amarillo + FS-01."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("historia_clinica.pdf", _historia_clinica), ("factura_medica.pdf", _factura_medica),
                 ("epicrisis.pdf", _epicrisis)]},
    "SIN-DEMO-024": {"extra": {"diagnostico": "Hernia discal lumbar — artrodesis",
        "procedimiento": "Artrodesis de columna lumbar",
        "nota_caratula": "Monto reclamado (26 000) supera la suma asegurada (25 000) → FS-14. Cirugía 8 días tras el inicio → FS-01."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("historia_clinica.pdf", _historia_clinica), ("factura_medica.pdf", _factura_medica),
                 ("informe_medico.pdf", _informe_medico), ("epicrisis.pdf", _epicrisis)]},
    "SIN-DEMO-025": {"extra": {"diagnostico": "Fractura de tibia — incapacidad temporal",
        "fecha_doc_inconsistente": "2026-04-17", "dias_incapacidad": "45",
        "tipo_evento": "Accidente laboral",
        "alerta_doc": "ALERTA — REQUIERE REVISIÓN: la fecha de emisión de este certificado (17/04/2026) es ANTERIOR a la fecha del accidente declarado (20/04/2026). Inconsistencia documental que activa RF-02.",
        "nota_caratula": "Certificado de incapacidad con fecha anterior al accidente → RF-02 (falsificación) post-revisión. Falta historia clínica (FS-08)."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("certificado_incapacidad.pdf", _certificado_incapacidad), ("parte_accidente.pdf", _parte_accidente)]},
    "SIN-DEMO-026": {"extra": {"causa_muerte": "Cardiopatía isquémica crónica", "manera_muerte": "Natural",
        "parentesco": "Hijo", "nota_caratula": "Muerte natural, póliza de ~5 años, beneficiario directo. Reclamo (40 000) bajo la suma asegurada (50 000)."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("certificado_defuncion.pdf", _certificado_defuncion), ("partida_defuncion.pdf", _partida_defuncion),
                 ("designacion_beneficiario.pdf", _designacion_beneficiario)]},
    "SIN-DEMO-027": {"extra": {"causa_muerte": "Politraumatismo por accidente", "manera_muerte": "Accidental",
        "parentesco": "Persona jurídica (no familiar)",
        "alerta_doc": "ALERTA — REQUIERE REVISIÓN: el beneficiario 'Inversiones Delta Capital S.A.' figura en la lista restrictiva de monitoreo antilavado. Coincidencia que activa RF-03 (lista restrictiva).",
        "nota_caratula": "Beneficiario corporativo en lista restrictiva → RF-03 rojo post-consulta. Póliza de 5 meses, suma elevada (80 000)."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("certificado_defuncion.pdf", _certificado_defuncion), ("partida_defuncion.pdf", _partida_defuncion),
                 ("designacion_beneficiario.pdf", _designacion_beneficiario), ("informe_forense.pdf", _informe_forense)]},
    "SIN-DEMO-028": {"extra": {"causa_muerte": "Traumatismo craneoencefálico (accidente de tránsito)", "manera_muerte": "Accidental",
        "parentesco": "Cónyuge",
        "nota_caratula": "Fallecimiento 1 día después del inicio de vigencia (03/05) → RF-05 piso amarillo + FS-01."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("certificado_defuncion.pdf", _certificado_defuncion), ("partida_defuncion.pdf", _partida_defuncion),
                 ("informe_forense.pdf", _informe_forense)]},
    "SIN-DEMO-029": {"extra": {"causa_muerte": "Insuficiencia respiratoria", "manera_muerte": "Natural",
        "parentesco": "Hijo",
        "nota_caratula": "Reclamo (49 500) = 99% de la suma asegurada → FS-14. Falta partida de defunción → FS-08."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("certificado_defuncion.pdf", _certificado_defuncion), ("designacion_beneficiario.pdf", _designacion_beneficiario)]},
    "SIN-DEMO-030": {"extra": {"causa_muerte": "Politraumatismo (accidente vial)", "manera_muerte": "Accidental",
        "parentesco": "Cónyuge",
        "nota_caratula": "Reporte 12 días tras el deceso → FS-12. Monto (55 000) bajo la suma asegurada (70 000)."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("certificado_defuncion.pdf", _certificado_defuncion), ("partida_defuncion.pdf", _partida_defuncion),
                 ("designacion_beneficiario.pdf", _designacion_beneficiario), ("informe_forense.pdf", _informe_forense)]},
    "SIN-DEMO-031": {"extra": {"tipo_evento": "Daños por agua", "origen_fuego": "—",
        "bienes": "Cielo raso y piso flotante de dormitorio",
        "conclusion_peritaje": "Daños por filtración compatibles con rotura de tubería declarada.",
        "nota_caratula": "Daño menor (900) sobre suma 35 000, póliza antigua, docs completos. Sin señales."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("informe_pericial_danos.pdf", _informe_pericial_danos), ("factura_reparacion.pdf", _factura_reparacion),
                 ("inventario_bienes.pdf", _inventario_bienes)]},
    "SIN-DEMO-032": {"extra": {"tipo_evento": "Incendio estructural", "origen_fuego": "Cortocircuito en tablero eléctrico",
        "bienes": "Mobiliario de cocina y estructura",
        "conclusion_peritaje": "Daños por fuego compatibles con origen eléctrico.",
        "nota_caratula": "Incendio 1 día tras el inicio de vigencia (01/05) → RF-05 piso amarillo + FS-01."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("informe_bomberos.pdf", _informe_bomberos), ("inventario_bienes.pdf", _inventario_bienes),
                 ("informe_pericial_danos.pdf", _informe_pericial_danos)]},
    "SIN-DEMO-033": {"extra": {"tipo_evento": "Incendio — pérdida total de bodega", "origen_fuego": "En investigación",
        "bienes": "Bodega anexa y contenido",
        "conclusion_peritaje": "Pérdida total de la bodega; valoración en el tope asegurado requiere verificación.",
        "nota_caratula": "Pérdida declarada (48 000) = 100% de la suma asegurada → FS-14. Siniestro 8 días tras inicio → FS-01."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("informe_bomberos.pdf", _informe_bomberos), ("inventario_bienes.pdf", _inventario_bienes),
                 ("informe_pericial_danos.pdf", _informe_pericial_danos)]},
    "SIN-DEMO-034": {"extra": {"bienes": "Electrodomésticos, equipos electrónicos y joyas",
        "obs_denuncia": "La denuncia fue presentada 6 días después del hecho. El plazo máximo en póliza para robo es de 4 días (RF-06). Falta comprobante de propiedad de las joyas (FS-08).",
        "nota_caratula": "Robo de contenidos con denuncia 6 días tarde → RF-06 piso amarillo + FS-02. Cobertura no PTxRB → sin RF-01."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("denuncia_sustraccion.pdf", _denuncia_sustraccion), ("inventario_bienes.pdf", _inventario_bienes)]},
    "SIN-DEMO-035": {"extra": {"tipo_evento": "Incendio en local comercial-vivienda", "origen_fuego": "En investigación",
        "bienes": "Mercadería y mobiliario del local",
        "concepto_factura": "Mercadería supuestamente destruida en el incendio",
        "alerta_doc": "ALERTA — REQUIERE REVISIÓN: la fecha de emisión de esta factura (28/04/2026) es POSTERIOR al incendio declarado (25/04/2026) y el informe de daños presenta valores tachados. Inconsistencias que activan RF-02.",
        "nota_caratula": "Factura emitida después del incendio + valores alterados → RF-02 rojo post-revisión. Reclamo 97.5% de la suma → FS-14."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("informe_bomberos.pdf", _informe_bomberos), ("inventario_bienes.pdf", _inventario_bienes),
                 ("factura_mercaderia.pdf", _factura_reparacion), ("informe_pericial_danos.pdf", _informe_pericial_danos)]},
    "SIN-DEMO-036": {"extra": {"bienes": "Pisos, muebles y electrodomésticos",
        "conclusion_peritaje": "Daños por filtración compatibles; proveedor de restauración recurrente en siniestros recientes.",
        "alerta_doc": "OBSERVACIÓN: el proveedor 'Restauraciones Integrales del Oro' aparece en múltiples reclamos recientes (también en SIN-DEMO-032). Activa FS-07 si la consulta confirma >2 casos observados.",
        "nota_caratula": "Reclamo (14 300) = 95.3% de la suma → FS-14. Proveedor recurrente → FS-07 post-consulta."},
        "docs": [("cedula_identidad.pdf", _build_cedula), ("caratula_poliza.pdf", _caratula_generica),
                 ("informe_pericial_danos.pdf", _informe_pericial_danos), ("factura_reparacion.pdf", _factura_reparacion),
                 ("inventario_bienes.pdf", _inventario_bienes)]},
}

for _cid, _cfg in NONVEHIC_CASES.items():
    _cfg["extra"].setdefault("cedula", _CEDULAS.get(_cid, "—"))
    CASES[_cid] = _cfg


def _json_path(stem: str) -> Path:
    """Locate a case JSON under json/<ramo>/<stem>.json (ramo-classified)."""
    matches = sorted(JSON_DIR.rglob(f"{stem}.json"))
    if not matches:
        raise FileNotFoundError(f"No JSON found for stem {stem!r} under {JSON_DIR}")
    return matches[0]


def _load_claim(claim_id: str) -> tuple[dict, str]:
    """Load claim JSON + merge extra fields. Returns (claim, ramo_folder)."""
    stem = _STEMS[claim_id]
    path = _json_path(stem)
    claim: dict = json.loads(path.read_text(encoding="utf-8"))
    claim.update(CASES[claim_id].get("extra", {}))
    return claim, path.parent.name


# claim_id → json filename stem (any ramo subfolder; resolved via rglob).
_STEMS: dict[str, str] = {
    "SIN-DEMO-007": "caso_07_falsificacion_docs",
    "SIN-DEMO-009": "caso_09_dinamica_imposible",
    "SIN-DEMO-012": "caso_12_robo_multi_senal",
    "SIN-DEMO-015": "caso_15_robo_total_critico",
    "SIN-DEMO-018": "caso_18_robo_total_fin_poliza",
    "SIN-DEMO-020": "caso_20_robo_parcial_amarillo",
    "SIN-DEMO-021": "caso_21_salud_verde_limpio",
    "SIN-DEMO-022": "caso_22_salud_docs_incompletos_late",
    "SIN-DEMO-023": "caso_23_salud_borde_vigencia",
    "SIN-DEMO-024": "caso_24_salud_monto_atipico",
    "SIN-DEMO-025": "caso_25_accidentes_personales_falsificacion",
    "SIN-DEMO-026": "caso_26_vida_verde_limpio",
    "SIN-DEMO-027": "caso_27_vida_beneficiario_restrictivo",
    "SIN-DEMO-028": "caso_28_vida_borde_vigencia",
    "SIN-DEMO-029": "caso_29_vida_monto_atipico_docs",
    "SIN-DEMO-030": "caso_30_vida_muerte_accidental_late_report",
    "SIN-DEMO-031": "caso_31_hogar_verde_limpio",
    "SIN-DEMO-032": "caso_32_incendio_borde_vigencia",
    "SIN-DEMO-033": "caso_33_incendio_monto_atipico",
    "SIN-DEMO-034": "caso_34_hogar_robo_contenidos_denuncia_tardia",
    "SIN-DEMO-035": "caso_35_incendio_falsificacion_docs",
    "SIN-DEMO-036": "caso_36_hogar_proveedor_recurrente",
}


def main() -> None:
    styles = _styles()
    total = 0

    for claim_id, case_cfg in CASES.items():
        claim, ramo = _load_claim(claim_id)
        claim_dir = OUTPUT_ROOT / ramo / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{claim_id} [{ramo}] — {claim['asegurado']} ({claim['ciudad']})")
        for filename, builder in case_cfg["docs"]:
            path = claim_dir / filename
            _write_pdf(path, builder, claim=claim, styles=styles)
            size_kb = path.stat().st_size // 1024
            print(f"  ✓ {path.relative_to(ROOT)}  ({size_kb} KB)")
            total += 1

    print(f"\nDone. {total} PDFs generados en {OUTPUT_ROOT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
