# Limitaciones, sesgos y riesgos

> Deliverable §2.3.5 / §2.4 / §2.10 — explicar de frente lo que el sistema NO puede hacer.
> Léase junto a [`uso_ia.md`](./uso_ia.md). Material obligatorio para el pitch (1 min "limitaciones y próximos pasos").

## 1. El sistema **alerta**, no acusa

El sistema **nunca** afirma que hubo fraude. Toda salida se enuncia como *"alerta"*, *"posible fraude"*, *"requiere revisión"*. La decisión final es **siempre** humana. Cualquier sticker, label o dashboard que diga "fraude" sin "posible" debe corregirse antes de la demo (§2.10).

## 2. Datos: 100% sintéticos

- El dataset que entrena los modelos y alimenta la demo está generado por `app/use_cases/generate_dataset/` a partir de 62 *archetypes* hand-crafted.
- No hay PII real. No hay datos confidenciales de Aseguradora del Sur.
- Las distribuciones de monto, fechas, ciudades, etc. son razonables pero **no calibradas con datos de producción**. Las métricas del modelo (AUC, calibración) reflejan ese sesgo: son válidas para validar la mecánica, no para predecir el comportamiento en producción.

## 3. Etiqueta `etiqueta_fraude_simulada`

- La etiqueta de entrenamiento se deriva del tier que el motor de reglas asigna al archetype (`1 si tier == 🔴`).
- Esto significa que el clasificador supervisado aprende — en parte — a imitar las reglas duras.
- Mitigación: excluimos del vector de features los flags que disparan reglas duras (ver `app/domain/ml/feature_names.py`), forzando al modelo a apoyarse en señales más suaves (frecuencias, montos, demoras, narrativa).
- Pero el techo de generalización está acotado por la calidad del generador de archetypes. **Un cliente real necesita reetiquetado humano** (anotador antifraude) antes de cualquier despliegue.

## 4. Volumen efectivo de entrenamiento

- 99 archetypes × 30 perturbaciones = **2.970 filas**, con tasa de positivos de sólo **7.9%** (la jitter empuja muchas variantes por debajo del umbral 🔴 → fuerte desbalance).
- 99 patrones distintos sigue siendo poco. Las perturbaciones son near-duplicates: el modelo verá variaciones pequeñas alrededor de pocos puntos en el espacio de features.
- La AUC-ROC medida es alta (**0.982 ± 0.017** en CV 5-fold, 0.980 holdout) precisamente *por* esa estructura near-duplicate: NO garantiza generalización a un mes de claims reales. Reportamos AUC-PR (0.971) y la matriz de confusión además de la AUC para no sobre-vender el número. Por el desbalance, el modelo se usa como **ranker** (opinión complementaria), no como clasificador binario — con el umbral 0.5 por defecto predeciría todo negativo (ver [`uso_ia.md`](./uso_ia.md) §"Calibración").

## 5. Riesgo de falsos positivos

Por el desbalance natural del dataset y por la naturaleza de las reglas duras (`RF-01` PTxRB → rojo automático), siniestros legítimos pueden caer en 🔴 / 🟡 simplemente por ser *atípicos*. La traffic-light **no es** una sentencia: es la cola de revisión del equipo antifraude.

Recomendaciones operativas:

- Medir tasa de falso positivo a 30/60 días de operación antes de ajustar pesos.
- Revisar mensualmente el rate de 🔴 que termina en `descartado` (workflow §6 V2.6) — un rate alto significa que el motor está produciendo demasiado ruido.
- No bloquear pagos automáticamente. La revisión humana es no-negociable (§2.2).

## 6. Sesgos potenciales

- **Geográfico:** archetypes están sobre-indexados a Guayaquil y Quito. Un sistema entrenado con datos reales debe rebalancearse.
- **Proveedores:** `proveedor_casos_observados` es un signal poderoso pero es proxy de "proveedor con histórico". Sin auditoría, esto puede penalizar talleres legítimamente populares.
- **Documentos:** `documentos_incompletos` puede correlacionar con segmentos socioeconómicos con menor acceso administrativo. **Monitorear la distribución de tier por segmento del asegurado**.

## 7. Datos faltantes / drift

- El backend no implementa detección de drift en producción. Si las distribuciones de input cambian (e.g. nuevos canales de venta), las métricas se degradan silenciosamente.
- Próximo paso post-hackathon: scheduled re-training mensual + alertas si el AUC en una ventana móvil cae > 5 puntos.

## 8. Componentes deliberadamente fuera de scope (entrega del hackathon)

Por enfoque y plazo (deadline 2026-05-29):

- Supabase Auth (usamos JWT local).
- File-upload + RAG ingestion.
- Long-term memory del agente.
- Router agent multi-task.
- Detección de drift en runtime.
- Pipeline de reentrenamiento automatizado.

Ver el design spec `docs/superpowers/specs/2026-05-26-centinela-claims-design.md` §11 para el trigger de re-introducción.

## 9. Lo que SÍ hacemos bien

Para que los puntos anteriores no se lean como derrotismo:

- **Separación rules vs. ML** — el analista ve dos opiniones independientes, no una cifra opaca (§2.4, 25% del puntaje).
- **Traceability** — cada alerta lista las reglas que dispararon (`code` + `evidence`).
- **SHAP top-3** — cuando el modelo opina, expone *por qué*.
- **`nearest_normal_claim_id`** — contraste con un caso conocido como normal.
- **Frase "posible fraude" enforced** — `ruff` flag manual + revisión de PR (§2 backend CLAUDE.md).
- **Human-in-the-loop por diseño** — el workflow §6 V2.6 obliga a un dictamen humano antes del cierre.

## Historial de conversaciones (agregado 2026-05-27)

La feature de "Historial de conversaciones" persiste los mensajes del agente Centinela IA por usuario en Postgres. Tiene limitaciones conocidas:

- **`conversations.user_id` sin FK** — los usuarios viven en la variable de entorno `AUTH_SEED_USERS`, no en una tabla. El `user_id` es un UUID determinístico (`uuid5(NAMESPACE_*, email)`) indexado pero sin restricción de integridad referencial. Cuando se migre a una tabla `users` real (post-hackathon, p.ej. con Supabase Auth), se agrega la FK.
- **El razonamiento del agente no se persiste.** Los eventos `tool_call`, `agent_step` y `tool_result` son artefactos de transparencia en vivo durante el SSE, no se almacenan. Recargar una conversación muestra sólo los textos `user` / `assistant`, no los pasos intermedios.
- **Sin paginación.** El sidebar lista hasta 200 conversaciones por usuario ordenadas por fecha reciente. Para escala hackathon es suficiente; en producción se introduce paginación o un índice de búsqueda dedicado.
- **Generación del título es fire-and-forget.** Existe una ventana corta donde el sidebar muestra "Sin título" hasta el siguiente refresh. Es una concesión consciente para no bloquear el stream SSE.
- **Tests de persistencia end-to-end están marcados `@pytest.mark.skip`** porque el cliente ASGI de tests no ejecuta el lifespan de FastAPI (el `session_factory` queda en None). El test es válido para ejecución manual contra un servidor en vivo: `uv run uvicorn app.main:app --port 8000` luego `pytest tests/agent/test_conversation_persistence.py -m integration -v`.
