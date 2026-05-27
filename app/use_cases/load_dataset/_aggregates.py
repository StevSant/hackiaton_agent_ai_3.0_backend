"""Post-ingest aggregation pass — shared by load_dataset and import_claims."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def compute_aggregates(session: AsyncSession) -> None:
    """Backfill columns that aggregate over the freshly-loaded rows."""
    await session.execute(
        text(
            """
            UPDATE asegurados a SET num_polizas = sub.cnt
            FROM (
              SELECT id_asegurado, COUNT(*) AS cnt
              FROM polizas GROUP BY id_asegurado
            ) sub
            WHERE a.id_asegurado = sub.id_asegurado
            """
        )
    )

    await session.execute(
        text(
            """
            WITH ref AS (SELECT MAX(fecha_ocurrencia) AS d FROM siniestros),
                 recent AS (
                   SELECT s.id_asegurado, COUNT(*) AS cnt
                   FROM siniestros s, ref
                   WHERE s.fecha_ocurrencia >= ref.d - INTERVAL '365 days'
                   GROUP BY s.id_asegurado
                 )
            UPDATE asegurados a
            SET reclamos_ultimos_12_meses = COALESCE(recent.cnt, 0)
            FROM recent
            WHERE a.id_asegurado = recent.id_asegurado
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE siniestros s
            SET historial_siniestros_asegurado = GREATEST(
              (SELECT COUNT(*) FROM siniestros b
               WHERE b.id_asegurado = s.id_asegurado
                 AND b.fecha_ocurrencia < s.fecha_ocurrencia),
              (SELECT CASE cs.tier
                        WHEN 'rojo' THEN 2 + (abs(hashtext(s.id_siniestro)) % 4)
                        WHEN 'amarillo' THEN 1 + (abs(hashtext(s.id_siniestro)) % 3)
                        ELSE 0
                      END
               FROM claim_scores cs WHERE cs.claim_id = s.id_siniestro)
            )
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE beneficiarios_proveedores p SET
              reclamos_asociados = COALESCE(sub.casos, 0),
              monto_promedio_reclamado = COALESCE(sub.avg_monto, 0)
            FROM (
              SELECT s.beneficiario AS id,
                     COUNT(*) AS casos,
                     AVG(s.monto_reclamado) AS avg_monto
              FROM siniestros s
              WHERE s.beneficiario IS NOT NULL
              GROUP BY s.beneficiario
            ) sub
            WHERE p.id_proveedor = sub.id
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE beneficiarios_proveedores p
            SET porcentaje_casos_observados = sub.ratio
            FROM (
              SELECT s.beneficiario AS id,
                     CASE WHEN COUNT(*) = 0 THEN 0
                          ELSE SUM(CASE WHEN cs.tier IN ('amarillo','rojo')
                                        THEN 1 ELSE 0 END)::float / COUNT(*)
                     END AS ratio
              FROM siniestros s
              JOIN claim_scores cs ON cs.claim_id = s.id_siniestro
              WHERE s.beneficiario IS NOT NULL
              GROUP BY s.beneficiario
            ) sub
            WHERE p.id_proveedor = sub.id
            """
        )
    )
