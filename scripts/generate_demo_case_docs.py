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
from datetime import date
from pathlib import Path

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
}


def _load_claim(claim_id: str) -> dict:
    """Load claim JSON and merge extra fields for PDF generation."""
    # Map claim_id to filename stem
    stem_map = {
        "SIN-DEMO-007": "caso_07_falsificacion_docs",
        "SIN-DEMO-009": "caso_09_dinamica_imposible",
        "SIN-DEMO-012": "caso_12_robo_multi_senal",
    }
    stem = stem_map[claim_id]
    path = JSON_DIR / f"{stem}.json"
    claim: dict = json.loads(path.read_text(encoding="utf-8"))
    extra = CASES[claim_id].get("extra", {})
    claim.update(extra)
    return claim


def main() -> None:
    styles = _styles()
    total = 0

    for claim_id, case_cfg in CASES.items():
        claim = _load_claim(claim_id)
        claim_dir = OUTPUT_ROOT / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{claim_id} — {claim['asegurado']} ({claim['ciudad']})")
        for filename, builder in case_cfg["docs"]:
            path = claim_dir / filename
            _write_pdf(path, builder, claim=claim, styles=styles)
            size_kb = path.stat().st_size // 1024
            print(f"  ✓ {path.relative_to(ROOT)}  ({size_kb} KB)")
            total += 1

    print(f"\nDone. {total} PDFs generados en {OUTPUT_ROOT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
