# Design — Isolated demo environment deployment (C17)

## Context

El sistema completo funciona, y funciona **sólo en un portátil**. `POST /api/ai/search` (C15) y el panel «Buscar con ayuda» (C16) están archivados; el corpus, los perfiles aprobados y los 1.200 documentos vectorizados viven en el Docker local. El §16 del diseño exige una URL pública con usuario de demostración, y no existe.

**Restricción que gobierna todo lo demás: no hay acceso a la cuenta AWS de la tienda.** Y aunque lo hubiera, tres hechos verificados en el repositorio harían el despliegue allí caro y arriesgado:

1. Su base de datos contiene el catálogo real de la joyería, sus puntos de venta y su personal.
2. `terraform/ec2.tf` declara `lifecycle { ignore_changes = [user_data] }`, y el script que despliega vive dentro de un `heredoc` de `user_data.sh`, escrito en el primer arranque de una instancia que lleva meses viva. Editarlo en el repositorio no propaga nada; re-ejecutar el script completo sobrescribiría `/etc/nginx/conf.d/jpv.conf`, que certbot ya modificó, y tiraría el TLS de la tienda.
3. Ese script inyecta **siete variables fijas**, ninguna de las cuales es `AiGateway__*` ni `IndexFeed__ApiKey`, y ejecuta `docker run` **sin `--network`**, de modo que el contenedor vive en el puente por defecto, donde Docker no resuelve nombres de contenedor.

En consecuencia el diseño no es «desplegar el servicio de IA junto al existente», sino **levantar un entorno completo y aislado en otra cuenta**, que además puede destruirse cuando deje de hacer falta.

Hay un segundo hecho que reordena el alcance: **el dato no existe fuera de local**. El plan lo dice tres veces. Un entorno perfecto con el índice vacío pasaría todas las pruebas y entregaría una URL inútil — la firma de A1 (C04) y B5 (C16), por tercera vez.

## Goals / Non-Goals

**Goals:**

- Una URL pública, con TLS válido y cuentas de demostración, donde el sistema completo funcione con el corpus cargado.
- Aislamiento **total** respecto a la cuenta de la tienda: ni infraestructura, ni permisos, ni flujos de despliegue, ni datos.
- Materializar la frontera público/privado sobre infraestructura real: el servicio que custodia la clave del proveedor no es alcanzable desde Internet.
- Que los dos fallos silenciosos posibles —modo de respuestas simuladas activo, y modelo de embeddings distinto del indexado— sean **visibles** en lugar de mudos.
- Reproducibilidad: ninguna etiqueta móvil en imágenes ni en herramientas de aprovisionamiento; el entorno se levanta en cualquier cuenta cambiando variables.
- Un aprovisionamiento del host tan pequeño que no sepa nada de la aplicación.

**Non-Goals:**

- Desplegar a la cuenta de la tienda, hoy o como parte de este change.
- Modificar la imagen de producción, el fichero de composición de desarrollo local o su capacidad asociada.
- Regenerar el contrato congelado del servicio de IA.
- Separar la sonda de salud en vida y disponibilidad (disparadores escritos abajo).
- Revertir el presupuesto temporal de recuperación de C16: se **mide y se anota**, no se corrige.
- Observabilidad de producción, alertas, panel de coste o pruebas A/B.
- Cualquier migración de esquema, de EF Core o de Alembic.

## Decisions

### D1 · Entorno de demostración autocontenido en otra cuenta, con estado propio

**Decisión.** Módulo de infraestructura en directorio y **estado separados**, apuntando a una cuenta AWS distinta.

**Alternativas consideradas.**

| Opción | Por qué se descarta |
|---|---|
| Segundo entorno en la instancia de la tienda | Exige reescribir el script de despliegue horneado, compartir memoria con el sistema del que depende un negocio y editar su configuración de proxy. Y no hay acceso |
| Base de datos separada dentro de la instancia gestionada existente | Obligaría a modificar el grupo de seguridad de producción, y ataría las copias de seguridad de ambos entornos: restaurar la demo a un punto anterior arrastraría a la tienda |
| Plataforma gestionada de contenedores | Es lo que los apuntes recomiendan de forma genérica y no es mala idea, pero son cuatro piezas redesplegadas en un modelo nuevo con muy poco margen, y los planes gratuitos duermen: quien abra la demo en frío espera casi un minuto |

El estado separado no es un detalle de organización: es lo que hace que un plan de infraestructura de la demo **no pueda ni siquiera proponer** un cambio sobre un recurso de la tienda.

### D2 · Base de datos con extensión vectorial en contenedor, no gestionada

**Decisión.** El mismo motor y la misma imagen que ya usa el fichero de composición de desarrollo, con volumen persistente.

**Por qué.** Vuelve **irrelevante** una verificación que el propio plan marcaba como obligatoria y que nunca llegó a ejecutarse: si el servicio gestionado admite instalar la extensión vectorial. El plan ya nombraba esta opción como su alternativa. La simetría con el entorno local es entonces exacta —el guion de aprovisionamiento del esquema y el camino de migraciones funcionan sin una sola variación—, y el dato de la demo es reproducible desde un volcado, así que las copias de seguridad gestionadas no compran nada.

**Coste asumido.** Sin copias gestionadas ni alta disponibilidad. Aceptable: la demo es reproducible por definición.

### D3 · Fichero de composición, y esta vez sí

El diseño general daba por hecho un fichero de composición en la instancia de producción. **No lo hay.** Sobre una instancia nueva, en cambio, describe los cuatro servicios en un sitio, da orden de arranque por dependencia y estado de salud, y crea la red sin intervención — que es exactamente lo que los apuntes piden. El coste es instalar el complemento correspondiente, que se resuelve en tres líneas.

**Alternativa descartada.** Dos invocaciones sueltas de contenedor más creación manual de red: es el patrón de producción, y su única ventaja —no tocar lo que funciona— no aplica en una instancia que no existe todavía.

### D4 · Fichero de composición **independiente**, no una extensión del de desarrollo

**Decisión.** Fichero autocontenido en la raíz. El de desarrollo no se toca.

**Por qué.** La capacidad viva que describe el entorno de desarrollo **fija literalmente la ruta del fichero y el nombre de la red** en dos de sus requisitos. Reorganizarlo obligaría a un delta sobre una capacidad viva, a corregir cinco documentos y a cambiar el flujo diario de trabajo, a cambio de elegancia.

**Coste asumido.** La topología queda descrita en dos ficheros. Se acepta a propósito, y a favor añade que un fichero cuyo nombre dice «demostración» no puede confundirse con el camino de producción.

### D5 · Terminación TLS automática en el proxy, en contenedor

**Decisión.** Proxy con emisión y renovación de certificado integradas, como un servicio más.

**Por qué.** Elimina el cliente de certificados del host, su tarea programada, el bloque de configuración escrito por `heredoc` y el paso manual posterior a la actualización de DNS. Y permite que el aprovisionamiento del host no sepa nada de dominios.

**Coste asumido.** Asimetría con producción, que usa otro proxy. No cuesta nada precisamente porque la demo es deliberadamente otro sistema, en otra cuenta.

### D6 · El nombre de dominio es un parámetro

**Decisión.** El nombre del anfitrión se inyecta. El entorno arranca con un nombre derivado de la dirección IP —que es un nombre DNS real y por tanto certificable— y migra al dominio propio cambiando un parámetro y redesplegando.

**Por qué.** Desacopla la entrega de una compra. El dominio deja de estar en el camino crítico.

### D7 · Sólo el proxy publica puertos

**Decisión.** Los otros tres servicios no declaran puertos publicados.

**Por qué.** La frontera queda escrita en el fichero, no en un documento. Y se cumple en **tres capas independientes**: el grupo de seguridad sólo abre los dos puertos del proxy, el proxy es el único servicio con puertos publicados, y el servicio de IA no publica ninguno. Un descuido en cualquiera de las tres no basta para exponer la clave del proveedor.

### D8 · Clasificación de la configuración en cuatro clases

**Decisión.**

| Clase | Dónde vive | Criterio |
|---|---|---|
| **A · Secreto** | Almacén cifrado → entorno del proceso → interpolación | Filtrarlo cuesta dinero o acceso |
| **B · Ajuste de entorno** | Almacén en claro, o el fichero de composición | Cambia entre entornos y no es confidencial |
| **C · Ajuste de comportamiento** | **Control de versiones**, como literal | No debería variar entre entornos; cambiarlo es un cambio de sistema |
| **D · Constante** | Imagen o fichero de composición | Ni confidencial ni variable |

**La decisión que más importa es la clase C.** El modelo de embeddings y el modo de respuestas simuladas **no son secretos**, y el almacén de parámetros es un sitio donde alguien puede cambiar un valor sin revisión de código. Estos dos exigen revisión de código **y reindexado**, así que van versionados.

**Alternativa descartada.** «Todo lo que varía, al almacén». Es la intuición habitual y produce exactamente el fallo que D9 previene.

### D9 · El modelo de embeddings se contrasta contra el índice

**Decisión.** La sonda de salud compara el modelo configurado con el que consta en las filas del índice, y declara un estado de discrepancia cuando difieren.

**Por qué.** Es el fallo más silencioso de todo el despliegue: consultas embebidas en un espacio y documentos en otro producen ruido, con respuesta correcta y sin traza. El índice **ya guarda el modelo por fila** desde C13, así que la comprobación no necesita esquema nuevo.

### D10 · Los secretos nunca tocan el disco

**Decisión.** El script de despliegue exporta los valores al entorno de su propio proceso y deja que el fichero de composición los interpole. No se escribe ningún fichero de entorno.

**Tres consecuencias operativas que hay que escribir, porque son fáciles de pasar por alto:**

- La traza de ejecución del intérprete queda **prohibida** en el tramo que lee secretos: la salida del comando remoto se conserva en el historial del servicio de administración.
- Cada variable requerida se valida explícitamente. Una variable **vacía** no falla: arranca un servicio que rechazará toda petición con un error de credenciales cuya causa el servicio tiene prohibido revelar.
- **Honestidad sobre el alcance:** las variables de entorno de un contenedor son legibles por el administrador del host. Es proporcionado para una demostración, y no debe describirse como una bóveda.

### D11 · Las parejas de secretos compartidos salen de un solo parámetro

**Decisión.** El secreto del token interno y la credencial del canal de indexación se leen **una vez** y se inyectan en los dos servicios que deben compartirlas.

**Por qué.** Dos parámetros distintos pueden derivar, y derivar produce un rechazo de credenciales cuya causa está especificado que no se revele. Un parámetro leído dos veces elimina la clase de fallo entera a coste cero.

### D12 · Salud enriquecida en el sitio, sin llamar al proveedor

**Decisión.** La sonda existente informa además de la base de datos, del índice y de si la credencial del proveedor está **configurada**. Conserva su tipo de retorno abierto.

**Por qué no consultar al proveedor.** Los apuntes lo desaconsejan dos veces, y con razón mecánica: una sonda que depende de un tercero convierte una indisponibilidad ajena en un despliegue fallido y, con un orquestador delante, en un reinicio en bucle. Ninguno de los tres consumidores de la sonda —el motor de contenedores, la verificación posterior al despliegue y la tarjeta del panel— necesita esa información. Lo que sí quieren saber es si **alguien olvidó configurar la credencial**, que es el fallo real.

**Por qué en el sitio y no en una ruta nueva.** Una ruta nueva, o un modelo de respuesta tipado, **mueven el contrato congelado** y rompen su prueba de deriva. Mantener el retorno abierto deja el contrato intacto.

**Coste asumido y escrito.** El contrato no describe la forma de la respuesta. Es la misma asimetría deliberada que ya existe con la ruta de evaluación, que el contrato publica y el perfil de producción no sirve.

**Cuándo se revisará esta decisión** — cualquiera de las tres, y no antes: cuando algo pueda **reiniciar el contenedor** según la respuesta; cuando la parte cara deje de ser cacheable barata; o cuando el servicio se despliegue a la cuenta real de la tienda. Al bifurcar, la ruta nueva regenera el contrato y rompe su prueba, que es lo correcto, porque la frontera se habrá movido.

### D13 · La sonda se cachea

**Decisión.** El resultado se reutiliza durante una ventana corta.

**Por qué.** El límite de conexiones del proyecto es de cinco, compartido. Una sonda que abre conexión en cada llamada podría ser lo que agote el conjunto durante un incidente: la sonda causando la avería que reporta.

### D14 · Endpoint de salud en el backend, fuera del disyuntor

**Decisión.** Ruta propia bajo el espacio de nombres de IA, restringida a administradores, servida por un cliente HTTP con nombre propio y **sin el disyuntor** del cliente principal.

**Por qué el endpoint.** El navegador **no puede** consultar al servicio de IA: es privado por diseño. Sin este salto no hay tarjeta posible.

**Por qué fuera del disyuntor.** Si la sonda compartiera el disyuntor, con el circuito abierto fallaría también — y su trabajo es precisamente diagnosticar cuando el camino principal está roto. Un cliente propio con tiempo de espera corto.

**Por qué sólo administradores.** La respuesta describe infraestructura. Un operador no tiene por qué saber cuántos documentos hay indexados.

### D15 · Imagen de demostración independiente, con base de rutas relativa

**Decisión.** Fichero de construcción propio para la API con su interfaz. El de producción **no se toca**.

**Por qué relativa.** La interfaz se sirve desde el mismo contenedor que la API, así que es mismo origen: verificado en el cliente HTTP y en el ayudante de rutas de imagen, donde la base se reduce a cadena vacía y devuelve rutas del mismo origen. La imagen queda **agnóstica del nombre de dominio** y sirve incluso sobre una dirección IP desnuda, lo que encaja con D6.

**Por qué no reutilizar la de producción.** Hornea la URL absoluta del dominio de la tienda en tiempo de construcción, así que la interfaz de la demo llamaría a la API de producción.

**Por qué no arreglar la de producción de paso.** Porque tocarla es tocar producción.

### D16 · Endurecer la imagen del servicio de IA, en su sitio

**Decisión.** Construcción multietapa, usuario sin privilegios, instalador de dependencias con **versión fijada** en lugar de una etiqueta móvil, y comprobación de salud propia.

**Por qué es seguro hacerlo aquí.** Esa imagen **no tiene ningún consumidor en producción**: hoy sólo la usa el fichero de composición de desarrollo. La etiqueta móvil del instalador es además un defecto de reproducibilidad real: el mismo commit produce imágenes distintas según el día.

**Detalle.** La comprobación de salud no debe instalar un cliente HTTP adicional sólo para eso; el intérprete que ya está en la imagen basta.

### D17 · Aprovisionamiento del host mínimo

**Decisión.** Cuatro pasos, sin nada específico de la aplicación: instalar el motor de contenedores y el complemento de composición con versión fijada, arrancar los servicios del sistema, traer el fichero de composición y el script, ejecutarlo.

**Por qué.** Es lo que hace el módulo portable entre cuentas: todo lo específico vive en el fichero de composición, en las imágenes y en el almacén de parámetros. Y evita reproducir el defecto de producción, donde el aprovisionamiento sabe de dominios, de proxy y de variables de la aplicación.

**Dos ajustes que lo completan.** La imagen base del sistema operativo se resuelve por un parámetro público del proveedor en lugar de una variable que hay que actualizar a mano, y se anota que el módulo asume la red por defecto de la cuenta.

### D18 · Límite de memoria en el servicio de IA

**Decisión.** Límite explícito en ese contenedor y sólo en ese.

**Por qué.** Convierte un agotamiento de memoria del anfitrión en uno del contenedor: se termina **sólo** el servicio de IA, su política de reinicio lo levanta, y el disyuntor degrada la búsqueda al camino léxico. Es la degradación ya diseñada, extendida a la capa de infraestructura.

**Detalle que se olvida.** La sección declarativa de recursos se **ignora** fuera de modo enjambre; hay que usar la directiva equivalente.

### D19 · El dato viaja por volcado, más una sincronización de reconciliación

**Decisión.** Volcado del esquema de negocio y del esquema vectorial desde el entorno local; restauración; y **una** sincronización que reconcilia y verifica ausencia de deriva.

**Por qué volcado y no recalcular.** No es sólo coste. Si el entorno público recalculase sus vectores, sería un índice **distinto** del que describen los números publicados, y esa diferencia es difícil de defender ante quien lea ambas cosas. La sincronización posterior existe para demostrar que el camino está cableado, que es lo que el volcado por sí solo no prueba.

**Y una sustitución obligatoria.** El volcado arrastra el personal real de la joyería, con sus correos. En un entorno público se sustituye por cuentas de demostración: una de administración y una de operación, para que se vean ambos paneles y el bloque de diagnóstico reservado a administradores. El catálogo real **sí** se publica: decisión de negocio tomada explícitamente.

### D20 · Rama de entorno y confianza acotada

**Decisión.** Rama de despliegue dedicada, emparejada con un entorno declarado en la plataforma de integración continua, y confianza federada **acotada a ese entorno**.

**Por qué.** El rol de producción confía en *cualquier* rama y *cualquier* flujo del repositorio. El de la demo puede ser más estricto sin coste. Y el entorno declarado es donde viven los secretos con ámbito y el historial de despliegues.

**Detalle de portabilidad.** El registro de confianza con el emisor de identidad es **único por cuenta y emisor**. En una cuenta nueva se crea; en una que ya lo tenga, hay que referenciarlo en lugar de declararlo, o el plan falla por entidad duplicada. Queda escrito porque es exactamente la clase de detalle que muerde meses después.

### D21 · Verificación posterior al despliegue desde dentro

**Decisión.** La comprobación se ejecuta dentro del anfitrión a través del servicio de administración, no desde el ejecutor de la canalización.

**Por qué.** El servicio es privado por diseño. Un ejecutor externo **no puede** alcanzarlo, y hacerlo alcanzable para poder comprobarlo destruiría lo que la comprobación pretende validar.

**Qué exige.** Base de datos accesible, **recuento de documentos mayor que cero**, ausencia de discrepancia de modelo, y credencial del proveedor configurada. El recuento mayor que cero es lo que impide dar por bueno un entorno vacío.

## Risks / Trade-offs

| Riesgo | Mitigación |
|---|---|
| **Entorno desplegado con el índice vacío.** Pasaría todas las pruebas y entregaría una URL inútil | El camino del dato entra en el change (D19) y la verificación exige recuento mayor que cero (D21) |
| **Modo de respuestas simuladas activo.** Devuelve respuestas fabricadas con apariencia de funcionar | Versionado como literal (D8, clase C), no en el almacén |
| **Modelo de embeddings distinto del indexado.** Ruido sin ningún error | Versionado como literal, y contrastado contra el índice en la sonda (D9), que además tiñe la tarjeta del panel |
| **Pérdida del volumen de certificados en un redespliegue.** La autoridad limita a cinco certificados duplicados por semana; dos descuidos dejan la demo sin TLS hasta la semana siguiente, con la entrega encima | Volumen persistente declarado; el script usa recreación en el sitio y **jamás** la orden que borra volúmenes; queda como aviso destacado en el ticket y en la historia |
| **Pérdida del volumen de datos.** Se pierde el corpus cargado | Mismo mecanismo, y además reproducible desde el volcado |
| **Memoria de la instancia con cuatro contenedores** | Límite en el servicio de IA (D18) más espacio de intercambio en el disco ya pagado; se mide tras el primer despliegue y se redimensiona si hace falta |
| **Secreto filtrado en el historial de comandos** | Traza de ejecución prohibida en el tramo que los lee (D10) |
| **Secreto vacío que arranca un servicio que rechaza todo** | Validación explícita de cada variable requerida (D10) |
| **Parejas de secretos que derivan** | Un solo parámetro leído dos veces (D11) |
| **Presupuesto de recuperación insuficiente** contra un proveedor a más latencia que un portátil | Se **mide y se anota**; corregirlo pertenece a los changes que trabajan en el paquete de recuperación |
| **Primera consulta lenta** por arranque en frío del cliente del proveedor | Llamada de calentamiento en el despliegue, antes de grabar nada |
| **Dominio no adquirido** | El nombre es un parámetro y existe un puente sin coste (D6) |

## Migration Plan

**No hay migración de esquema.** Ni de EF Core ni del servicio de IA más allá de la actualización de revisiones que ya existe.

**Despliegue, en orden:**

1. Alta de la cuenta y credenciales de administración. *(Prerrequisito externo; bloquea todo lo demás.)*
2. Plan y aplicación del módulo de infraestructura. **Verificación explícita: el plan no lista ningún recurso ajeno al módulo.**
3. Primer arranque del anfitrión; comprobar que queda registrado en el servicio de administración.
4. Carga de parámetros, secretos incluidos.
5. Primer despliegue con la base de datos vacía. Aprovisionamiento del esquema vectorial con privilegios de administrador, y actualización de revisiones.
6. Camino del dato: volcado, sustitución de cuentas, restauración, sincronización de reconciliación.
7. Verificación posterior y calentamiento.
8. Migración del nombre de anfitrión al dominio propio, cuando exista.

**Reversión.** Cada paso es reversible por separado. El entorno completo se destruye con una orden, y el coste se detiene. **La reversión no puede afectar a la tienda por construcción**, porque no comparten estado, cuenta ni recursos.

**Puntos de parada si la sesión desborda**, en orden de valor entregado: (1) infraestructura, aprovisionamiento, composición, canalización y despliegue con corpus y TLS — **archivable**; (2) salud enriquecida con contraste de modelo; (3) endpoint del backend y tarjeta del panel; (4) endurecimiento de la imagen, exclusiones de contexto y deprecaciones.

## Open Questions

Ninguna bloqueante de producto: las decisiones se cerraron en la sesión de exploración del 2026-08-29 y están registradas en el §0 del plan de changes.

| # | Cuestión | Estado |
|---|---|---|
| 1 | Alta de la cuenta de demostración | **Prerrequisito externo.** Bloquea el despliegue real, no la escritura del código ni de las pruebas |
| 2 | Compra del dominio | **No bloqueante** por D6. Criterios de elección anotados en la historia |
| 3 | Dimensionado definitivo de la instancia | Se decide **con la medición** del primer despliegue, no antes |
| 4 | Retención del entorno tras la corrección | Pendiente. Por defecto se mantiene hasta la evaluación y se destruye después |

**Criterio por defecto** si el apply descubre un detalle menor no listado: la opción más estrecha que **no** toque la cuenta de la tienda, **no** modifique la imagen de producción ni el fichero de composición de desarrollo, **no** regenere el contrato congelado, **no** abra migración y **no** adelante trabajo de otros changes.
