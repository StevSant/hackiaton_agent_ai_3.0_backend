#!/usr/bin/env python3
"""Generate uploadable PDF document packages for the casos_demo set.

Per-case content (which docs, alert text, diagnoses, etc.) is **data**, kept in
``data/config/demo_case_packages.json`` — NOT hardcoded here. This module only
holds the PDF *templates* (builder functions) exposed via the ``BUILDERS``
registry; the config references them by string key.

Output: data/casos_demo/sample_documents/<ramo>/<claim_id>/*.pdf

Each package contains 4-7 PDFs named so ``sync_claim_document._FILENAME_TIPO_HINTS``
can infer the tipo from the filename keyword.

Usage::

    uv run python scripts/generate_demo_case_docs.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Progress output uses ✓ — force UTF-8 so it doesn't crash on Windows cp1252.
sys.stdout.reconfigure(encoding="utf-8")

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
    body_fn=lambda c: (
        f"<b>Nota analítica:</b> {c['nota_caratula']}" if c.get("nota_caratula") else None
    ),
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
        ("Conclusión", c.get("conclusion_peritaje", "Daños compatibles con el siniestro")),
    ],
    alert_fn=lambda c: c.get("alerta_doc"),
    doc_code="DOC-INFORME-PERICIAL",
)


# ---------------------------------------------------------------------------
# Builder registry — maps the string keys used in
# data/config/demo_case_packages.json to the builder functions above.
# Add a new builder here when you add a new document template.
# ---------------------------------------------------------------------------

BUILDERS: dict[str, object] = {
    # vehiculos
    "cedula": _build_cedula,
    "matricula": _build_matricula,
    "acta": _build_acta,
    "caratula_poliza": _build_caratula_poliza,
    "peritaje": _build_peritaje,
    "denuncia": _build_denuncia,
    "proforma_caso07": _build_proforma_caso07,
    "proforma_generic": _build_proforma_generic,
    # salud / vida / hogar
    "caratula_generica": _caratula_generica,
    "historia_clinica": _historia_clinica,
    "factura_medica": _factura_medica,
    "informe_medico": _informe_medico,
    "epicrisis": _epicrisis,
    "certificado_incapacidad": _certificado_incapacidad,
    "parte_accidente": _parte_accidente,
    "certificado_defuncion": _certificado_defuncion,
    "partida_defuncion": _partida_defuncion,
    "designacion_beneficiario": _designacion_beneficiario,
    "informe_forense": _informe_forense,
    "informe_bomberos": _informe_bomberos,
    "inventario_bienes": _inventario_bienes,
    "factura_reparacion": _factura_reparacion,
    "denuncia_sustraccion": _denuncia_sustraccion,
    "informe_pericial_danos": _informe_pericial_danos,
}

# Per-case package content lives in config (data/, not hardcoded here).
_PACKAGES_PATH = ROOT / "data" / "config" / "demo_case_packages.json"


def _load_packages() -> dict:
    """Load the per-case package spec from data/config/demo_case_packages.json."""
    payload = json.loads(_PACKAGES_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, dict):
        raise RuntimeError(f"Malformed package config at {_PACKAGES_PATH}: missing 'cases' object")
    return cases


def _json_path(stem: str) -> Path:
    """Locate a case JSON under json/<ramo>/<stem>.json (ramo-classified)."""
    matches = sorted(JSON_DIR.rglob(f"{stem}.json"))
    if not matches:
        raise FileNotFoundError(f"No JSON found for stem {stem!r} under {JSON_DIR}")
    return matches[0]


def main() -> None:
    styles = _styles()
    cases = _load_packages()
    total = 0

    for claim_id, cfg in cases.items():
        path = _json_path(cfg["stem"])
        ramo = path.parent.name  # json/<ramo>/<stem>.json → ramo bucket
        claim: dict = json.loads(path.read_text(encoding="utf-8"))
        claim.update(cfg.get("extra", {}))

        claim_dir = OUTPUT_ROOT / ramo / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{claim_id} [{ramo}] — {claim['asegurado']} ({claim['ciudad']})")
        for doc in cfg["docs"]:
            builder = BUILDERS[doc["builder"]]
            out_path = claim_dir / doc["filename"]
            _write_pdf(out_path, builder, claim=claim, styles=styles)
            size_kb = out_path.stat().st_size // 1024
            print(f"  ✓ {out_path.relative_to(ROOT)}  ({size_kb} KB)")
            total += 1

    print(
        f"\nDone. {total} PDFs generados en {OUTPUT_ROOT.relative_to(ROOT)}/ "
        f"(config: {_PACKAGES_PATH.relative_to(ROOT)})"
    )


if __name__ == "__main__":
    main()
