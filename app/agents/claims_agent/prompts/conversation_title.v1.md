Generas un **título breve** para una conversación de análisis de siniestros.
A partir del intercambio (pregunta del analista + respuesta), devuelve un título
que capture el tema concreto de la conversación.

Reglas:
- En **español**, máximo **6 palabras**.
- Sin emojis, sin comillas, sin punto final.
- Específico, no genérico: prefiere "Top 10 casos de mayor riesgo" sobre
  "Consulta de siniestros". Si la conversación gira en torno a un caso, proveedor
  o ciudad concretos, nómbralo.
- Si la pregunta es muy genérica, deriva el título del contenido de la respuesta.
- Devuelve **solo el título**, nada más.

Pregunta:
{query}

Respuesta:
{answer}

Título:
