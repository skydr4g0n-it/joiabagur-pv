## 1. Puerta de entrada y línea base del borrado

- [ ] 1.1 Verificar que **C25 está archivado** y su tabla de ablations publicada en `ai-service/evals/results/`. **Si no lo está, parar**: este change retiraría el andamio mientras sostiene la tabla
- [ ] 1.2 Leer del informe de C25 qué variante de ponderación adaptativa **ganó** el barrido, y qué valores quedaron congelados
- [ ] 1.3 Medir la línea base de la suite **antes de tocar nada**: `uv run pytest`, guardando los **nombres** de los tests que fallan y no su recuento
- [ ] 1.4 Guardar la tabla publicada de C25 como referencia de comparación para la verificación de la tarea 4

## 2. Inventario de lo que se retira, comprobado y no recordado

- [ ] 2.1 Buscar sobre el árbol todos los lectores de cada perilla candidata: ruta viva, configuraciones de evaluación supervivientes y tests que ejerzan comportamiento vivo
- [ ] 2.2 Escribir el inventario en el `design.md` del change **antes de borrar**: qué se retira, y el motivo por el que cada elemento no tiene lector
- [ ] 2.3 Confirmar que **no** entran en el inventario las perillas que siguen teniendo lector: pesos de negocio, umbral de distancia, `k` y profundidad — son el mecanismo de calibración de C26 y C38

## 3. El borrado

- [ ] 3.1 `retrieval/orchestrator.py` — retirar la rama del modo plano y la perilla que lo seleccionaba
- [ ] 3.2 `config/settings.py` — retirar los pesos por lista y las perillas del inventario de 2.2
- [ ] 3.3 `config/settings.py` — hacer que una configuración que nombre una perilla retirada **falle nombrándola**, en lugar de ignorarla en silencio
- [ ] 3.4 Retirar la variante de ponderación adaptativa perdedora, con su perilla y sus tests
- [ ] 3.5 `evals/configs.py` — `v2-hibrido` deja de ser ejecutable; conservar el YAML con una cabecera que declare que es **histórico** (opción por defecto de la pregunta abierta 4), porque el informe lo cita por identificador
- [ ] 3.6 Retirar los tests del comportamiento retirado, incluido `test_flat_fusion_mode_reproduces_the_published_baseline`
- [ ] 3.7 Añadir el test que fija el borrado: `test_no_flat_fusion_path_exists` y `test_no_per_list_weight_is_defined`
- [ ] 3.8 Añadir `test_a_configuration_naming_a_retired_knob_fails_loudly`

## 4. Verificación de que el borrado no movió nada

- [ ] 4.1 `uv run pytest`: comparar los **nombres** de los tests que fallan con la línea base de 1.3; deben caer exactamente los del comportamiento retirado y **ninguno más**
- [ ] 4.2 Re-ejecutar la tabla de ablations **una vez**, sobre la misma versión del golden set
- [ ] 4.3 Comparar las filas supervivientes con la tabla de 1.4: **las cifras deben ser idénticas**. Cualquier diferencia, por pequeña que sea, es un fallo del borrado — se revierte y se investiga, no se discute
- [ ] 4.4 Verificar que `ai-service/openapi.json` queda **sin diff** y que no hay migración
- [ ] 4.5 Verificar que `backend/`, `frontend/`, `terraform/` y `.github/workflows/` quedan **sin diff**
- [ ] 4.6 Comprobar que ninguna configuración de despliegue (`.env`, SSM, `docker-compose`) trae una perilla retirada

## 5. Documentación, y sólo con las cifras idénticas delante

- [ ] 5.1 `ai-service/README.md` — declarar que la fila de la línea base es **histórica y no re-ejecutable**, con el enlace a su informe y a su JSONL
- [ ] 5.2 `ai-service/README.md` — retirar la documentación del modo plano y de las perillas retiradas
- [ ] 5.3 `ai-service/tests/README.md` — los tests que caen y los que se añaden
- [ ] 5.4 Informe corto en `Documentos/Proyecto Final AIEng/informes/` con el inventario retirado y la comparación de cifras de 4.3
- [ ] 5.5 Entrada fechada en el §0 y ficha propia en `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md`
- [ ] 5.6 Actualizar `Documentos/epicas.md` (estado del change y recuento)
- [ ] 5.7 `openspec validate --all --strict` en **`0 failed`**
- [ ] 5.8 `/opsx:verify` antes de archivar, con atención a que ninguna cifra se haya movido
