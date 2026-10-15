# Reglas de trabajo

## Eficiencia de contexto y verificación

- Priorizar scripts reproducibles, búsquedas dirigidas y resultados estructurados. Mostrar resúmenes, errores y métricas relevantes; guardar logs completos y artefactos privados bajo `.local/`.
- Agrupar consultas independientes y evitar releer documentación o repetir verificaciones ya aprobadas salvo cambios, fallos o incertidumbre nueva.
- Usar logs, marcadores de carga, PID, jerarquía accesible y métricas para automatizar navegación y mediciones. No capturar pantallas en cada paso ni sondear procesos sin necesidad.
- Reservar comprobaciones visuales para establecer una escena desconocida, resolver navegación ambigua, investigar una anomalía o validar equivalencia visual tras cambios gráficos. Reutilizar referencias y comparar imágenes mediante scripts antes de inspeccionarlas manualmente.
- Ahorrar tokens no justifica omitir pruebas funcionales, equivalencia x86, protección de partidas ni las mediciones físicas necesarias. No afirmar equivalencia visual o rendimiento basándose únicamente en logs o tests parciales.
- Comunicar avances breves: hallazgo, evidencia y siguiente acción. Evitar volcar archivos completos, inventarios extensos o salidas repetidas en el chat.
