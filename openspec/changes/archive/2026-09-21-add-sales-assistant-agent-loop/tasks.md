## 1. Puerta de entrada

- [x] 1.1 Medir la línea base de la suite de `ai-service` **por nombres de test** (`git stash push -u`, `uv run pytest`, `git stash pop`) y guardar la lista de nombres, no el recuento
- [x] 1.2 Ejecutar `openspec validate --all --strict` y confirmar `0 failed` **antes** de tocar nada
- [x] 1.3 Guardar el `sha256` de `ai-service/openapi.json` en el informe, para poder verificar el movimiento del contrato al cierre en vez de suponerlo
- [x] 1.4 Confirmar que `assist/tools.py` sigue sin ser importado desde `jbg_ai.api`, que es lo que hoy hace estructural la ausencia de contrato de C32a

## 2. Vocabularios y presupuestos

- [x] 2.1 Añadir a `assist/constants.py` los seis presupuestos, **derivando el de llamadas al proveedor de las constantes de sus tres tramos** y nunca escribiéndolo como dígito
- [x] 2.2 Añadir el vocabulario cerrado de **motivos de parada**: sin más herramientas, presupuesto de iteraciones, de herramientas, de tokens, de reloj, y aclaración
- [x] 2.3 Añadir la quinta causa de fallo de tool, `presupuesto_agotado`, y actualizar la tupla cerrada que la suite recorre exhaustivamente
- [x] 2.4 Añadir las dos constantes de versión de prompt, con la ruta **derivada** de la versión y nunca escrita al lado, como ya hace `assist/prompt.py`
- [x] 2.5 Comprobar que `constants.py` **sigue sin importar nada**, que es la propiedad que permite que todo lo demás lea de él sin ciclo

## 3. El puerto del agente

- [x] 3.1 Definir en `assist/agent_llm.py` el tipo de una llamada a herramienta (identificador, nombre, argumentos) y el tipo de un paso: llamadas, coste y motivo de finalización, **sin ningún campo capaz de llevar prosa**
- [x] 3.2 Definir el `Protocol` del puerto, con el cliente inyectable por constructor para que ningún test abra un socket
- [x] 3.3 Implementar el adaptador: temperatura cero, **sin `response_format`**, `tools` desde `registry.schemas()`, sin capa de reintentos que se solape con la del proveedor, y *timeout* explícito por llamada
- [x] 3.4 Descartar el texto del modelo **en la frontera del adaptador** y registrar en el log su longitud y su digest, nunca el texto
- [x] 3.5 Importar la librería del proveedor **dentro de la llamada** y no en el módulo, para que el paquete siga siendo importable sin proveedor — el test que lo lee ya existe
- [x] 3.6 Tests del puerto: que el tipo no declara campo de texto, que el adaptador descarta la prosa, y que un fallo del proveedor degrada en vez de escapar

## 4. La transcripción

- [x] 4.1 Crear `assist/transcript.py` con el tipo de turno y su rol, y los tres topes: número de turnos, caracteres por turno y **caracteres totales**
- [x] 4.2 Aplicar el delimitado `QUERY_OPEN`/`QUERY_CLOSE` **a cada turno**, reutilizando las marcas de C30b en vez de definir otras
- [x] 4.3 Tratar los turnos atribuidos al asistente como dato del cliente, bajo los mismos topes y el mismo delimitado que los del operario
- [x] 4.4 Tests: inyección en el turno 3 que no mueve el mensaje de sistema; turno de asistente falsificado tratado como dato; y rechazo antes de cualquier llamada al proveedor cuando se excede un tope

## 5. El bucle

- [x] 5.1 Crear `assist/agent.py` con la firma de librería —puertos y clientes **inyectados**, nunca construidos aquí— para que el arnés pueda montarlo con dobles, como hace con `assist_sale`
- [x] 5.2 Implementar la vuelta: decidir, recoger las llamadas del paso, ejecutar, observar, acumular en el contexto y en la evidencia
- [x] 5.3 Ejecutar las llamadas de una vuelta **concurrentemente con tope de 4**, emparejando cada observación con el identificador de su llamada
- [x] 5.4 Implementar las tres condiciones de parada: sin llamadas a herramienta, aclaración (**terminal**), y agotamiento de cualquiera de los seis presupuestos
- [x] 5.5 Implementar el recorte de llamadas que no caben: ejecutar las que quepan **en el orden emitido**, devolver el resto como observación con `presupuesto_agotado` **sin tocar puerto**, y parar tras esa vuelta
- [x] 5.6 Emitir siempre un motivo de parada del vocabulario cerrado, y nunca dejar que el consumidor lo deduzca de los contadores
- [x] 5.7 Añadir la aserción en ejecución del techo de llamadas al proveedor, al modo de la que C31 dejó en el orquestador
- [x] 5.8 Tests del bucle, uno por condición de parada y uno por presupuesto, con el doble del puerto decidiendo qué pide el modelo en cada vuelta

## 6. El guardarraíl de entrada

- [x] 6.1 Clasificar **exactamente un turno por petición**, el que se contesta, reutilizando `classify_query()` sin modificarlo
- [x] 6.2 Cortocircuitar ante un veredicto de rechazo **en cualquier turno**, emitiendo los dos códigos que C31 distingue y sin ejecutar herramienta ni recuperación
- [x] 6.3 **No** actuar sobre el veredicto de insuficiencia y **no** usar el veredicto de índice; dejar constancia en el código de por qué, para que un lector futuro no lo tome por un olvido
- [x] 6.4 Tests: una sola clasificación sea cual sea la longitud de la transcripción; deriva en el último turno rechazada sin gastar herramientas; y seguimiento elíptico que **no** se cortocircuita por insuficiencia

## 7. La evidencia y la generación

- [x] 7.1 Implementar el acumulador: candidatos, sustitutos, miembros de familia y citas vistos a lo largo de las vueltas, con **tope de piezas distintas** que llegan al *payload*
- [x] 7.2 Marcar los grupos de sustitutos con un valor de vocabulario cerrado que los separe de las coincidencias de catálogo
- [x] 7.3 **Excluir toda etiqueta de disponibilidad** del *payload*, con un test que lo compruebe sobre una petición que sí observó disponibilidad
- [x] 7.4 Proyectar la evidencia al *payload* de consulta libre reutilizando `free_query_payload_from()` tal cual, sin duplicar su construcción
- [x] 7.5 Llamar a `generate_pitch()` con la tarea nueva, y aplicar la misma regla de C30b: las citas publicadas son las que el argumentario declaró y verificaron
- [x] 7.6 Implementar la abstención de esta ruta: cierta **sólo si** corrió al menos una búsqueda, todas abstuvieron y no hay ninguna cita

## 8. Los prompts

- [x] 8.1 Escribir `prompts/agent/v1.md`: qué herramientas hay, cuándo pivotar a sustitutos, cuándo pedir aclaración, y que su prosa se descarta
- [x] 8.2 Escribir `prompts/assist/v4.md` como v3 más la sección de tarea de evidencia del agente, que explica qué es un grupo de sustitutos
- [x] 8.3 Dejar `prompts/assist/v3.md` **intacto** y añadir el test que impide editarlo por accidente, replicando el que ya protege a v1 y v2
- [x] 8.4 Test de que cada versión declarada corresponde al fichero que se carga, replicando `test_prompt_version_matches_the_loaded_prompt_file`

## 9. El contrato y la ruta

- [x] 9.1 Definir `AgentAssistRequest` con la transcripción y sus topes declarados en el esquema, y `pos_id` aceptado e ignorado como en el resto de `/v1`
- [x] 9.2 Definir `AgentAssistResponse` **como subclase** de `AssistResponse`, con parcial, motivo de parada, contadores, traza acotada, versión del prompt del bucle y objeto de uso propio que publica el recuento de llamadas
- [x] 9.3 Añadir `POST /v1/assist/agent` con su comportamiento bajo `STUB_MODE` y el mismo mapeo de errores a códigos HTTP que usa la ruta de venta
- [x] 9.4 Resolver el cliente del agente con cadena de respaldo `agente → argumentario → enriquecimiento`, registrando **una vez por proceso** qué eslabón ganó y sin secreto en la línea
- [x] 9.5 Servir sin bucle y **sin error** cuando no hay credencial: es el *fail-open*, la ablación y el *rollback*
- [x] 9.6 Añadir los ajustes nuevos a `Settings` y **fijarlos en `canonical_openapi_settings()`**, para que un valor exportado no se cuele en el *snapshot* comprometido
- [x] 9.7 Regenerar `ai-service/openapi.json` y **verificar hoja a hoja** que el movimiento es adición pura, con la forma de `AssistResponse` pinchada como conjunto
- [x] 9.8 Test de que `POST /v1/assist/sale` responde **idéntico**, campo a campo y techo a techo

## 10. La traza y la observabilidad

- [x] 10.1 Construir la traza rica en proceso: por iteración, herramientas, argumentos, observaciones, coste y latencia
- [x] 10.2 Derivar de ella la traza del cable **quitando argumentos y contenidos de observación**, y dejarla siempre presente
- [x] 10.3 Emitir la línea de log con contadores, motivo de parada, coste y latencia, **nunca la transcripción ni un argumento**, propagando `trace_id` a cada vuelta
- [x] 10.4 Tests: la traza del cable no contiene ningún argumento ni ningún fragmento de observación, y el log tampoco

## 11. Las specs

- [x] 11.1 Revisar la delta `## MODIFIED` de `sales-assistant-tools` contra la spec viva: el bloque copiado debe ser el **entero**, no un extracto
- [x] 11.2 Revisar la delta `## ADDED` de `sales-assistant-agent` contra lo implementado, corrigiendo lo que la implementación haya refutado
- [x] 11.3 Ejecutar `openspec validate --all --strict` y confirmar `0 failed` — la forma completa, no la de un solo change

## 12. Los instrumentos de medición

- [x] 12.1 Escribir el guion que genera el **set de carga** (~60-100 transcripciones sintéticas), sembrado del vocabulario real del catálogo, y declarar en el fichero que mide acumulación y no calidad
- [x] 12.2 Escribir a mano el **set de calibración** (~15-20 transcripciones) con la herramienta esperada en cada turno, incluyendo escenarios de pieza agotada contra el punto de venta con más exposición a agotados
- [x] 12.3 Declarar el set de calibración como **`calibration-only`** en su propia cabecera, para que el change de evaluación no lo reutilice sin darse cuenta
- [x] 12.4 Dejar constancia explícita de que **el golden set no se toca**, ni para calibrar ni para iterar prompts

## 13. La pasada con proveedor real

- [x] 13.1 Crear `evals/agent_sweep.py` al modo de `evals/assist_sweep.py`: procedencia (`run_id`, `git_sha`, versiones de prompt, modelo, recuento de índice), `--dry-run`, `--limit` y política de bucle de eventos de Windows
- [x] 13.2 Ejecutar los **dos brazos de modelo** sobre los **dos conjuntos** en la misma ejecución, escribiendo un artefacto JSON versionado
- [x] 13.3 Preparar el entorno: exportar el almacén de certificados a un PEM que incluya la raíz del interceptor TLS y apuntar `SSL_CERT_FILE` a él — **sin esto toda llamada muere con `CERTIFICATE_VERIFY_FAILED`**
- [x] 13.4 Ejecutar `--dry-run` primero y una **prueba de humo de tres transcripciones** después, antes de la pasada larga
- [x] 13.5 Ejecutar la pasada completa y conservar el artefacto en `evals/results/`

## 14. Análisis y fijación de los números

- [x] 14.1 Calcular p50 y p95 de tokens, de contexto en caracteres y de reloj, y **fijar los tres presupuestos** con esas cifras
- [x] 14.2 Publicar la **curva de crecimiento del contexto por vuelta**, que es lo que dice si hay que compactar
- [x] 14.3 Publicar el coste por brazo de modelo y el **sobrecoste del agente frente al pipeline** sobre entrada comparable
- [x] 14.4 Responder la pregunta de granularidad: herramientas nunca elegidas, causas de argumento recurrentes, **nombres de herramienta inventados** y llamadas consecutivas casi idénticas
- [x] 14.5 Responder la pregunta de la etiqueta: tasa de pivote a sustitutos **por etiqueta**, separando el sobre-pivote del infra-pivote
- [x] 14.6 Declarar como limitación, con su motivo, cualquiera de las dos preguntas que la pasada no consiga responder — nunca heredarla en silencio

## 15. Cierre

- [x] 15.1 Volver a correr la suite y comparar **por nombres de test** contra la línea base de 1.1, sin retirar ni renombrar ninguno
- [x] 15.2 Verificar el movimiento de `openapi.json` contra el `sha256` de 1.3 y confirmar que la diferencia es exactamente la ruta nueva y sus modelos
- [x] 15.3 Trazar los **catorce escenarios** de HU-AIENG-032b a test nombrado, en una tabla del informe
- [x] 15.4 Escribir el informe de implementación con lo que la implementación **refute** de la historia y del ticket, siguiendo el patrón de los diez anteriores
- [x] 15.5 Actualizar la documentación: `Documentos/epicas.md`, plan de changes, `ai-service/README.md`, `ai-service/tests/README.md`, `openspec/config.yaml` y `.env.example`
- [x] 15.6 Anotar en la ficha del change de evaluación lo que esta pasada le deje escrito, y en `DEFERRED_TASKS.md` la política de *timeout* y de circuito de la ruta nueva en la capa .NET, que queda identificada y no hecha
