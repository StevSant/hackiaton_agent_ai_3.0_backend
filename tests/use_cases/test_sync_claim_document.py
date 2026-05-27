"""Unit tests for document sync helpers."""

from app.use_cases.sync_claim_document import infer_document_tipo


def test_infer_document_tipo_from_filename() -> None:
    assert infer_document_tipo("01_solicitud_siniestro.pdf") == "Solicitud de siniestro"
    assert infer_document_tipo("03_acta_policial.pdf") == "Acta policial"
    assert infer_document_tipo("random_scan.jpg") == "Documento adjunto"
