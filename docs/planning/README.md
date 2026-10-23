# Control persistente del proyecto

`backlog.json` es la única fuente de estados, estimaciones, responsables, dependencias y evidencia. `BACKLOG.md` y `GANTT.md` se generan; no editarlas manualmente. Cada cláusula importada conserva su texto y origen completo, aunque sea contexto de capacidades existentes; no equivale a un módulo implementado. Las épicas S00–S15 y tareas de entrega se distinguen con `work_kind`. `covered_by` enlaza cobertura; una lista vacía permanece sin entrega asignada. El registro de criterios A–P permite revisar el cierre de S01.

Al comenzar: leer planificación y decisiones, revisar Git/código/pruebas, registrar alcance y supuestos. Al cerrar: actualizar criterios con pasa/falla/no ejecutado, evidencias, bloqueos, previsión e historial; registrar hallazgos aunque se difieran. No actualizar la línea base para esconder desviaciones. `DECISIONS.md` registra decisiones, no copia estados.

```text
python scripts/planning.py
python scripts/planning.py --check
```

La comprobación rechaza IDs repetidos, dependencias inexistentes/cíclicas, criterios vacíos y vistas divergentes. Los IDs del manifest inicial no pueden desaparecer. Para añadir tareas: nuevo ID, fuente exacta, campos obligatorios, vínculos y evento de historial; no reutilizar. Para dividir: conservar original y enlazar hijas; para sustituir/duplicar: conservar ID con vínculo al canónico; diferido/cancelado sigue visible. Las copias de fuentes son evidencia congelada, no listas maestras editables.

Las fechas vacías significan sin estimar; estimación de trabajo y espera externa son distintas. Mermaid incluye hitos con fecha conocida, sin barras de duración inventada, y precedencias; la tabla mantiene todos los requisitos. No existe una promesa de salida a producción.

Lee [revisión inicial](INITIAL_REVIEW.md), [evidencia de entrega](VALIDATION_S00_S01.md), [procedimiento de equipo](../team-access.md) y [actualización Windows](../windows-update-s01.md). Una nueva entrega debe conservar estos vínculos e historial.
