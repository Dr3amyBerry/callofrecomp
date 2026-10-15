# Investigación WSA x86_64

**Misión activa:** alcanzar 120 FPS sostenidos de motor sin recortar calidad ni precisión. El panel virtual medido es de 75 Hz y no demuestra 120 presentaciones/s.

**Última aplicación real:** [enlace local R/MEM/U/PC sobre el conjunto previo](WSA_POSTOPT_APPLICATION_2026-10-15.md), A/B/A/B de 65,75→68,15 FPS y 15,2125→14,675 ms CPU/frame. El [conjunto previo](WSA_CUMULATIVE_2026-10-15.md) A/B/A/B pasó de 54,75→66,75 FPS; **no sumar porcentajes de pruebas diferentes**.

Las anteriores investigaciones [CPU de la APK](WSA120_OPTIMIZED_APK_CPU_PROFILE_2026-10-15.md), [región x87](WSA120_NATIVE_X87_STATE_2026-10-15.md) y [limitador](WSA120_LIMITER_AND_RENDERER_PROFILE_2026-10-15.md) son fundamentos medidos con distintos ELFs. Ver [estado global](../../PROJECT_STATUS.md) y [registro de mejoras](../../OPTIMIZATION_LEDGER.md).

**Seguridad:** CFG14 y el atajo de `double` antiguo están bloqueados; nunca reactivarlos por posible aumento FPS.
