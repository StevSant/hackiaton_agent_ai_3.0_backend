#!/usr/bin/env python3
"""Generate sample PDF documents that an Ecuador insurer typically receives for fraud review.

Output: data/sample_documents/<claim_id>/*.pdf + manifest.json + checklist PDF.

Usage:
    uv run --with reportlab python scripts/generate_sample_claim_pdfs.py
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
OUTPUT_ROOT = ROOT / "data" / "sample_documents"

CLAIM = {
    "id": "SIN-2026-08412",
    "asegurado": "María Fernanda Salazar Torres",
    "cedula": "1712345678",
    "poliza": "PV-7782341",
    "ramo": "Vehículos",
    "cobertura": "Pérdida total por robo",
    "ciudad": "Quito",
    "sucursal": "Quito Norte",
    "fecha_ocurrencia": "18/04/2026",
    "fecha_reporte": "03/05/2026",
    "fecha_denuncia": "30/04/2026",
    "monto_reclamado": 38500.00,
    "suma_asegurada": 42000.00,
    "vehiculo_marca": "Toyota",
    "vehiculo_modelo": "Fortuner",
    "vehiculo_anio": 2023,
    "vehiculo_placa": "PCH-4821",
    "vehiculo_chasis": "MR0HZ8CD4P0123456",
    "vehiculo_motor": "2GD-998877",
    "proveedor": "Taller Mecánico Auto-Élite",
    "proveedor_ruc": "1790123456001",
}


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


def _header_block(story: list, styles: dict[str, ParagraphStyle], title: str, issuer: str) -> None:
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


def _footer(story: list, styles: dict[str, ParagraphStyle], doc_code: str) -> None:
    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            f"Documento de muestra · Aseguradora del Sur · {doc_code} · "
            f"Siniestro {CLAIM['id']} · Generado {date.today():%d/%m/%Y}",
            styles["footer"],
        )
    )


def _write_pdf(path: Path, builder) -> None:
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
    styles = _styles()
    story: list = []
    builder(story, styles)
    doc.build(story)


def build_solicitud_siniestro(story, styles) -> None:
    _header_block(story, styles, "SOLICITUD DE ATENCIÓN DE SINIESTRO", "Aseguradora del Sur S.A.")
    story.append(
        _key_value_table(
            [
                ("N.º siniestro", CLAIM["id"]),
                ("Fecha de reporte", CLAIM["fecha_reporte"]),
                ("Sucursal receptora", CLAIM["sucursal"]),
                ("Asegurado", CLAIM["asegurado"]),
                ("Cédula / RUC", CLAIM["cedula"]),
                ("Póliza", CLAIM["poliza"]),
                ("Ramo", CLAIM["ramo"]),
                ("Cobertura afectada", CLAIM["cobertura"]),
                ("Fecha de ocurrencia", CLAIM["fecha_ocurrencia"]),
                ("Lugar", f"{CLAIM['ciudad']} — sector La Carolina"),
                ("Monto reclamado (USD)", f"${CLAIM['monto_reclamado']:,.2f}"),
            ]
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Relato del asegurado", styles["section"]))
    story.append(
        Paragraph(
            "El día 18 de abril de 2026, aproximadamente a las 02:15, el vehículo asegurado "
            "fue sustraído mientras se encontraba estacionado frente al domicilio del asegurado. "
            "No hubo testigos presenciales ni registro inmediato en cámaras de seguridad del edificio. "
            "El asegurado tomó conocimiento del hecho al día siguiente en horas de la mañana.",
            styles["body"],
        )
    )
    story.append(Paragraph("Documentos adjuntos declarados", styles["section"]))
    story.append(
        Paragraph(
            "Denuncia fiscal, matrícula vehicular, cédula de identidad, carátula de póliza, "
            "licencia de conducir. Se indica que el acta policial y el certificado de endoso "
            "serán remitidos posteriormente.",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-001-SOLICITUD")


def build_denuncia_fiscal(story, styles) -> None:
    _header_block(story, styles, "DENUNCIA POR DELITO DE ROBO", "Fiscalía General del Estado — DMQ")
    story.append(
        _key_value_table(
            [
                ("N.º expediente", "FGED-2026-045871"),
                ("Fecha de presentación", CLAIM["fecha_denuncia"]),
                ("Delito denunciado", "Robo de vehículo motorizado"),
                ("Denunciante", CLAIM["asegurado"]),
                ("Cédula", CLAIM["cedula"]),
                ("Bien sustraído", f"{CLAIM['vehiculo_marca']} {CLAIM['vehiculo_modelo']} {CLAIM['vehiculo_anio']}"),
                ("Placa", CLAIM["vehiculo_placa"]),
                ("Chasis", CLAIM["vehiculo_chasis"]),
                ("Fecha del hecho", CLAIM["fecha_ocurrencia"]),
            ]
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        Paragraph(
            "<b>Observación de control interno:</b> La denuncia fue presentada 12 días después "
            "de la fecha reportada de ocurrencia. El plazo operativo de la aseguradora para robo "
            "total es de 4 días calendario.",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-002-DENUNCIA-FISCAL")


def build_acta_policial(story, styles) -> None:
    _header_block(story, styles, "ACTA DE PRIMER RESPONDIENTE", "Policía Nacional — Subzona Norte DMQ")
    story.append(
        _key_value_table(
            [
                ("N.º acta", "PN-DMQ-2026-118902"),
                ("Fecha de levantamiento", "— pendiente original —"),
                ("Distrito", "Metropolitano de Quito"),
                ("Tipo de evento", "Robo / hurto vehicular"),
                ("Placa reportada", CLAIM["vehiculo_placa"]),
                ("Estado del documento", "COPIA NO CERTIFICADA — DOCUMENTO INCOMPLETO"),
            ]
        )
    )
    story.append(
        Paragraph(
            "Este PDF simula el tipo documental exigido por la unidad antifraude. "
            "En el caso demo el acta policial original figura como <b>faltante</b> en la bandeja.",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-003-ACTA-POLICIAL")


def build_matricula(story, styles) -> None:
    _header_block(story, styles, "MATRÍCULA VEHICULAR", "Agencia Nacional de Tránsito — ANT")
    story.append(
        _key_value_table(
            [
                ("Placa", CLAIM["vehiculo_placa"]),
                ("Marca / Modelo", f"{CLAIM['vehiculo_marca']} {CLAIM['vehiculo_modelo']}"),
                ("Año", str(CLAIM["vehiculo_anio"])),
                ("Color", "Plata metalizado"),
                ("Clase", "SUV"),
                ("Chasis", CLAIM["vehiculo_chasis"]),
                ("Motor", CLAIM["vehiculo_motor"]),
                ("Propietario", CLAIM["asegurado"]),
                ("Identificación", CLAIM["cedula"]),
                ("Estado registral", "ACTIVO"),
            ]
        )
    )
    _footer(story, styles, "DOC-004-MATRICULA")


def build_cedula(story, styles) -> None:
    _header_block(story, styles, "CÉDULA DE IDENTIDAD — COPIA", "Registro Civil del Ecuador")
    story.append(
        _key_value_table(
            [
                ("Nombres y apellidos", CLAIM["asegurado"]),
                ("N.º cédula", CLAIM["cedula"]),
                ("Nacionalidad", "Ecuatoriana"),
                ("Estado civil", "Casada"),
                ("Domicilio", "Quito — La Carolina"),
                ("Fecha de expedición", "12/08/2021"),
            ]
        )
    )
    _footer(story, styles, "DOC-005-CEDULA")


def build_caratula_poliza(story, styles) -> None:
    _header_block(story, styles, "CARÁTULA DE PÓLIZA", "Aseguradora del Sur S.A.")
    story.append(
        _key_value_table(
            [
                ("N.º póliza", CLAIM["poliza"]),
                ("Contratante", CLAIM["asegurado"]),
                ("Ramo", CLAIM["ramo"]),
                ("Plan", "Integral Plus Vehículos"),
                ("Vigencia desde", "28/03/2026"),
                ("Vigencia hasta", "28/03/2027"),
                ("Suma asegurada", f"${CLAIM['suma_asegurada']:,.2f}"),
                ("Cobertura principal", CLAIM["cobertura"]),
                ("Deducible robo", "10% del valor asegurado"),
            ]
        )
    )
    story.append(
        Paragraph(
            "<b>Nota analítica:</b> El siniestro ocurre 21 días después del inicio de vigencia (RF-05).",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-006-CARATULA-POLIZA")


def build_licencia(story, styles) -> None:
    _header_block(story, styles, "LICENCIA DE CONDUCIR — COPIA", "Agencia Nacional de Tránsito — ANT")
    story.append(
        _key_value_table(
            [
                ("Titular", CLAIM["asegurado"]),
                ("N.º licencia", "B-1712345678"),
                ("Tipo", "B — vehículos livianos"),
                ("Fecha de expedición", "05/01/2024"),
                ("Fecha de caducidad", "05/01/2029"),
                ("Restricciones", "Ninguna"),
            ]
        )
    )
    _footer(story, styles, "DOC-007-LICENCIA")


def build_certificado_endoso(story, styles) -> None:
    _header_block(story, styles, "CERTIFICADO DE ENDOSO / PROPIEDAD", "Notaría Décima — Quito")
    story.append(
        _key_value_table(
            [
                ("Estado", "NO PRESENTADO — PLACEHOLDER DEMO"),
                ("Vehículo", f"{CLAIM['vehiculo_placa']} · {CLAIM['vehiculo_marca']} {CLAIM['vehiculo_modelo']}"),
                ("Beneficiario preferente", "Aseguradora del Sur S.A."),
                ("Observación", "Documento requerido para pago de pérdida total"),
            ]
        )
    )
    story.append(
        Paragraph(
            "En producción este documento acreditaría el endoso a favor de la aseguradora. "
            "Para el caso demo se marca como <b>faltante</b> (AF-02).",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-008-CERTIFICADO-ENDOSO")


def build_peritaje(story, styles) -> None:
    _header_block(story, styles, "INFORME DE PERITAJE TÉCNICO", "Perito independiente — Ing. Carlos Mendoza")
    story.append(
        _key_value_table(
            [
                ("Referencia", f"PER-{CLAIM['id']}"),
                ("Fecha de inspección", "09/05/2026"),
                ("Vehículo", f"{CLAIM['vehiculo_marca']} {CLAIM['vehiculo_modelo']} · {CLAIM['vehiculo_placa']}"),
                ("Valor comercial referencial", "$41,200.00"),
                ("Conclusión preliminar", "Evidencia compatible con sustracción total"),
                ("Observaciones", "Sin rastros de forzamiento en domicilio reportado"),
            ]
        )
    )
    _footer(story, styles, "DOC-009-PERITAJE")


def build_proforma_taller(story, styles) -> None:
    _header_block(story, styles, "PROFORMA DE REPUESTOS Y MANO DE OBRA", CLAIM["proveedor"])
    story.append(
        _key_value_table(
            [
                ("RUC proveedor", CLAIM["proveedor_ruc"]),
                ("Referencia", "PRO-2026-88412"),
                ("Fecha", "10/05/2026"),
                ("Concepto", "Repuestos originales + mano de obra estimada"),
                ("Subtotal", "$36,800.00"),
                ("IVA", "$4,416.00"),
                ("Total", "$41,216.00"),
            ]
        )
    )
    story.append(
        Paragraph(
            "<b>Alerta antifraude:</b> Proveedor PRV-0142 (Auto-Élite) en lista restrictiva interna (RF-03).",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-010-PROFORMA")


def build_comprobante_reporte(story, styles) -> None:
    _header_block(story, styles, "COMPROBANTE DE REPORTE DE SINIESTRO", "Aseguradora del Sur — Canal digital")
    story.append(
        _key_value_table(
            [
                ("N.º siniestro", CLAIM["id"]),
                ("Canal", "App móvil / sucursal digital"),
                ("Fecha y hora de registro", "03/05/2026 09:42"),
                ("Analista asignado", "Unidad de Siniestros Vehículos"),
                ("Estado inicial", "En reserva — documentación en revisión"),
            ]
        )
    )
    _footer(story, styles, "DOC-011-COMPROBANTE")


def build_checklist_general(story, styles) -> None:
    _header_block(
        story,
        styles,
        "CHECKLIST DOCUMENTAL — PAQUETE TÍPICO ASEGURADORA",
        "Centinela IA · Análisis de fraude",
    )
    rows = [
        ["#", "Tipo documento", "Ramo", "Obligatorio", "Uso en fraude"],
        ["1", "Solicitud / aviso de siniestro", "Todos", "Sí", "Validar relato y fechas"],
        ["2", "Cédula de identidad / RUC", "Todos", "Sí", "Identidad del reclamante"],
        ["3", "Carátula / condiciones de póliza", "Todos", "Sí", "Cobertura, vigencia, endoso"],
        ["4", "Denuncia fiscal / policial", "Robo, hurto", "Sí", "Plazos, consistencia temporal"],
        ["5", "Acta policial / parte", "Robo, accidente", "Sí", "Dinámica del hecho"],
        ["6", "Matrícula vehicular", "Vehículos", "Sí", "Propiedad, datos técnicos"],
        ["7", "Licencia de conducir", "Vehículos", "Sí", "Habilitación del conductor"],
        ["8", "Certificado de endoso", "Pérdida total", "Sí", "Beneficiario aseguradora"],
        ["9", "Peritaje / inspección", "Vehículos, hogar", "Frecuente", "Valoración y daños"],
        ["10", "Proforma / factura taller", "Reparación", "Frecuente", "Montos atípicos, proveedor"],
        ["11", "Historial médico", "Salud", "Sí", "Preexistencias, sobre-tratamiento"],
        ["12", "Informe bomberos", "Incendio", "Condicional", "Causa y extensión del daño"],
        ["13", "Guía de remisión", "Transporte carga", "Condicional", "Mercadería afectada"],
        ["14", "Comprobante de reporte", "Todos", "Sí", "Trazabilidad operativa"],
    ]
    table = Table(rows, colWidths=[1 * cm, 5.5 * cm, 2.8 * cm, 2.2 * cm, 4.8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            f"Paquete generado para el caso demo <b>{CLAIM['id']}</b> en "
            f"<i>{OUTPUT_ROOT / CLAIM['id']}</i>.",
            styles["body"],
        )
    )
    _footer(story, styles, "DOC-000-CHECKLIST")


DOCUMENTS: list[tuple[str, str, str, callable]] = [
    ("01_solicitud_siniestro.pdf", "Solicitud de siniestro", "entregado", build_solicitud_siniestro),
    ("02_denuncia_fiscal.pdf", "Denuncia fiscal", "entregado_demora", build_denuncia_fiscal),
    ("03_acta_policial.pdf", "Acta policial", "faltante_demo", build_acta_policial),
    ("04_matricula_vehicular.pdf", "Matrícula del vehículo", "entregado", build_matricula),
    ("05_cedula_identidad.pdf", "Cédula de identidad", "entregado", build_cedula),
    ("06_caratula_poliza.pdf", "Carátula de póliza", "entregado", build_caratula_poliza),
    ("07_licencia_conducir.pdf", "Licencia de conducir", "entregado", build_licencia),
    ("08_certificado_endoso.pdf", "Certificado de endoso", "faltante_demo", build_certificado_endoso),
    ("09_peritaje_tecnico.pdf", "Peritaje técnico", "entregado", build_peritaje),
    ("10_proforma_taller.pdf", "Proforma de taller", "entregado", build_proforma_taller),
    ("11_comprobante_reporte.pdf", "Comprobante de reporte", "entregado", build_comprobante_reporte),
]


def main() -> None:
    claim_dir = OUTPUT_ROOT / CLAIM["id"]
    claim_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, str | bool]] = []
    for filename, tipo, estado, builder in DOCUMENTS:
        path = claim_dir / filename
        _write_pdf(path, builder)
        manifest.append(
            {
                "filename": filename,
                "tipo": tipo,
                "estado_demo": estado,
                "claim_id": CLAIM["id"],
                "mime_type": "application/pdf",
                "falta_en_caso": estado.startswith("faltante"),
            }
        )
        print(f"  ✓ {path.relative_to(ROOT)}")

    checklist_path = OUTPUT_ROOT / "00_checklist_documental_aseguradora.pdf"
    _write_pdf(checklist_path, build_checklist_general)
    print(f"  ✓ {checklist_path.relative_to(ROOT)}")

    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "claim_id": CLAIM["id"],
                "asegurado": CLAIM["asegurado"],
                "generated_at": date.today().isoformat(),
                "documents": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  ✓ {manifest_path.relative_to(ROOT)}")
    print(f"\nGenerados {len(manifest)} PDFs + checklist en {OUTPUT_ROOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
