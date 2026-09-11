# C25 — mediciones de la implementación: la abstención no cabe en un escalar

**Sesión del 2026-09-11**, sobre la rama `c25-recalibrate-ranking-and-abstention`, con la base
levantada. Éstas son las cuatro mediciones que la exploración dejó **pendientes de fase 0** por
exigir base de datos, más la verificación de entorno que las habilita.

A diferencia de la exploración —que se hizo con el contenedor apagado y marcó como pendiente todo
lo que exigía base—, aquí **todo sale de ejecutar contra el índice vivo**. Donde una cifra tiene
predicción previa en [`c25-exploration-measurements.md`](c25-exploration-measurements.md), se
contrasta explícitamente contra ella.

---

## 0. Resumen

| # | Medición | Resultado | Qué decide |
|---|---|---|---|
| **M1** | `min(distancia)` por consulta | **Las dos poblaciones se solapan por completo**: `máx(contestables) = 0,7118` contra `mín(fuera) = 0,4469` | Regla **relativa por consulta** → **fase D**. La ventana **no se mueve** |
| **M2** | Cobertura con el denominador corregido | Las cuatro categorías protegidas dan **1,00 exacto**; con el ingenuo darían 0,64–0,88 | El denominador corregido es **obligatorio**, y el riesgo número uno queda cuantificado |
| **M3** | Hermanas de familia en el top-10 | **14 de 48** consultas (29,2 %) tienen 3+ hermanas; **nunca más de 4** de 10 huecos | Penalización de variante **refutada**; `groups[]` **sube de prioridad** en C30/C36 |
| **M4** | Reparto de `1-2` frente a `3+` | `1-2` es el **3,4 %** de los pares no nulos (191 contra 5.431) | Binario **confirmado**: no hay masa sobre la que calibrar |
| **M5** | Qué reordena la rotación | Como desempate estricto, **0 pares** del top-5; como clave, **11.067** inversiones con el 71,2 % a más de diez puestos | La rotación **se retira del orden**: se lee para diagnóstico |
| **M6** | Rejilla del peso de disponibilidad | **Invariante**: siete valores, cifras idénticas | Lo calibrado es el **signo**, no el valor |

**M5 y M6 no estaban planificadas**: salen de ejecutar el barrido y son las dos únicas que
**refutan el diseño** en lugar de confirmarlo. Están registradas aquí y en D10 del `design.md`.

**Ninguna cifra contradice la exploración.** Las cinco predicciones de cobertura de D8 reproducen
al decimal, y el `23,54 %` de `sales_30d` no nulo se confirma exactamente. Lo que M1 añade es una
respuesta que la exploración declaró desconocida, no una corrección.

---

## Verificación de entorno (tarea 1.1)

La exploración avisaba de que C23 se exploró con el contenedor apagado y hubo que corregir cifras
después. Antes de medir nada:

| Condición | Resultado |
|---|---|
| Base en el 5433, documentos vivos | **1.168**, todos con `embedding` no nulo |
| `ai.pos_projection` drenada | **6.050** pares asignados sobre **11** puntos de venta |
| `HT-ARTRUTX` | **0** asignados — excluido de la validación (tarea 1.2) |
| Clave de *embeddings* | **operativa**, HTTP 200, dimensión 1536 |
| `SSL_CERT_FILE` | **reconstruido**; ver la nota de abajo |

**El paquete de certificados había caducado.** El `jpv-ca-bundle.pem` del 7 de septiembre ya no
cubría la CA que intercepta el TLS de esta máquina, y el fallo se presentaba exactamente con el
síntoma engañoso que el README describe: `OpenAIException - Connection error`, que no nombra ni
TLS ni certificados. Reconstruido desde el almacén de raíces de Windows concatenado con
`certifi`, la clave responde 200. **Es un problema de máquina de desarrollo y no toca el código.**

**La línea base publicada se reproduce exactamente**, lo cual verifica el entorno de punta a punta
antes de tocar la fusión:

| lectura | C24 publicado | reproducido hoy |
|---|---:|---:|
| `v2-hibrido` global | 0,603 | **0,603** |
| `tuning` | 0,942 | **0,942** |
| `new` | 0,535 | **0,535** |

El reparto de ceros por punto de venta también coincide con lo que C22 midió: **MAO-AIR 34,4 %**
(143 de 416), **FORNELLS 12,0 %** (29 de 241), **HT-GALDANA 11,7 %** (55 de 469).

---

## M1 · La distribución que decide la abstención

Medida espejando la rama vectorial viva de `search.py` —mismo predicado de compatibilidad de
modelo, misma expresión de distancia— pero **sin el umbral de 0,65**, porque lo que se busca es el
mejor acierto real de cada consulta, incluidas las que hoy no devolverían nada.

| población | n | mín | p25 | mediana | p75 | **máx** |
|---|---:|---:|---:|---:|---:|---:|
| contestables | 43 | 0,2071 | 0,3197 | 0,3983 | 0,5817 | **0,7118** |
| fuera de dominio | 5 | **0,4469** | 0,4535 | 0,5025 | 0,5558 | 0,6042 |

### El veredicto del criterio pre-registrado

El criterio quedó escrito en D11 **antes de mirar esta distribución** (tarea 1.4): se adopta la
forma escalar **si y sólo si `máx(contestables) < mín(fuera)`**.

```
   máx(contestables) = 0,7118        mín(fuera) = 0,4469
   0,7118 < 0,4469  →  FALSO         hueco = −0,2649
```

**No hay solape parcial: hay contención.** El rango entero de las cinco de fuera de dominio
—[0,4469 ; 0,6042]— cae **dentro** del rango de las contestables. Un escalar no puede separarlas
porque no hay nada que separar.

El coste de intentarlo, consulta a consulta:

| umbral | de las 5 de fuera, calla | de las 43 contestables, silencia |
|---:|---:|---:|
| 0,4469 | 5 | **19** |
| 0,4535 | 4 | 19 |
| 0,5025 | 3 | 17 |
| 0,5558 | 2 | 12 |
| 0,6042 | 1 | 6 |
| **0,65 (vivo)** | **0** | 5 |

Callar las cinco cuesta **19 de 43 contestables, el 44 %**. Y la última fila explica de dónde salía
el `0,000` de abstención que C24 publicó en las tres configuraciones: **el umbral vivo no alcanza a
ninguna de las cinco** — mientras que ya silencia cinco contestables.

Las cinco de fuera de dominio, ordenadas:

| distancia | qid | texto |
|---:|---|---|
| 0,4469 | `q46` | un rosario de plata |
| 0,4535 | `q47` | un dedal de plata de coleccion |
| 0,5025 | `q44` | un reloj de plata sumergible |
| 0,5558 | `q48` | una hucha de plata para bautizo |
| 0,6042 | `q45` | piercing de ombligo de acero quirurgico |

**Por qué se solapan, y por qué era previsible sin ser predecible.** Las cinco son *plausibles en
joyería* por construcción de la categoría, y cuatro de las cinco dicen literalmente «de plata» —
vocabulario que el catálogo tiene a espuertas. La distancia coseno mide parecido semántico, y «un
rosario de plata» **se parece** mucho a un catálogo de plata: lo que falla no es el parecido, es que
la pieza concreta no existe. Es justo lo contrario del corpus de conocimiento de C23, donde lo de
fuera de dominio era de *otro dominio*.

Y las contestables que quedan lejos no son ruido, son las difíciles legítimas: `q02` *la lagartija
que toma el sol en las paredes* (0,7118), `q32` *para llevar a diario* (0,6931), `q41` **`SKU98`**
(0,6909) — un código de producto, que es léxicamente exacto y semánticamente opaco.

### Consecuencia sobre la secuencia (tarea 2.2)

> **El trabajo del umbral va a la FASE D.** La regla es **relativa por consulta**, se aplica
> **después** de la fusión y **no altera el conjunto de candidatos**. Las ventanas capturadas en la
> fase B siguen siendo válidas durante toda la fase C.

Esto es lo que D12 quería asegurar: la asignación de fase se decide por una medición y no por
conveniencia. Y abarata el change —no hay que re-fijar nada en el `WHERE`— a cambio de encarecer la
fase D, donde ahora vive todo el trabajo de abstención.

**Nota sobre el tamaño de la muestra.** Con n=5 estas cifras no sostienen una tasa de aceptación, y
por eso la tarea 12.1 amplía la categoría a 15-20. Lo que **sí** sostienen es la elección de forma:
la contención es total y no marginal, así que ninguna consulta añadida va a convertir un solape de
−0,2649 en separabilidad.

---

## M2 · La cobertura, y el denominador que era el riesgo número uno

Numerador: coordinación del mejor documento de la lista expandida. Denominador **corregido**: grupos
contables cuya `tsquery` no es vacía, vía `numnode(<fragmento>) > 0`. Denominador **ingenuo**: todos
los grupos contables.

| categoría | n | **cobertura corregida** | cobertura ingenua | mínimo corregido |
|---|---:|---:|---:|---:|
| `variante-talla` | 7 | **1,000** | 0,655 | 1,000 |
| `materiales` | 5 | **1,000** | 0,640 | 1,000 |
| `piedra` | 4 | **1,000** | 0,667 | 1,000 |
| `sinonimos` | 6 | **1,000** | 0,861 | 1,000 |
| `lexico-exacto` | 4 | **1,000** | 0,875 | 1,000 |
| `subjetiva` | 5 | 0,900 | 0,229 | 0,500 |
| `fuera-de-dominio` | 5 | 0,417 | 0,223 | 0,250 |
| `descripcion-sin-anclaje` | 12 | **0,292** | 0,148 | 0,000 |

**La predicción de D7 se cumple y es falsable.** Las cuatro categorías que la regla existe para no
tocar —`materiales`, `sinonimos`, `lexico-exacto`, `piedra`— dan **1,000 exacto en todas y cada una
de sus 19 consultas**, sin una sola excepción. Su peso léxico queda intacto y su nDCG@5 debe moverse
en exactamente cero.

**Y el riesgo número uno queda cuantificado.** Con el denominador ingenuo esas mismas categorías
darían 0,640 / 0,861 / 0,875 / 0,667: la regla les recortaría entre el **12 % y el 36 %** del peso
léxico. `materiales` puntúa nDCG@5 0,968 y `lexico-exacto` 1,000 — la regla destruiría exactamente
lo que existe para proteger, y el agregado global podría subir igual y taparlo.

**Aparece una quinta categoría en cobertura 1,00 que el diseño no listaba:** `variante-talla` (0,655
ingenua). El gate de la tarea 4.4 debe cubrirla también, porque su predicción de efecto cero es
idéntica.

La regla dispara donde tenía que disparar: `descripcion-sin-anclaje`, la categoría más grande y la
que el híbrido hunde de 0,431 a 0,172, promedia **0,292** de cobertura.

| qid | coord/den | corregida | ingenua | texto |
|---|---|---:|---:|---|
| `q07` | 0/4 | 0,000 | 0,000 | la raiz retorcida de un arbol viejo |
| `q09` | 0/2 | 0,000 | 0,000 | el fruto de la encina |
| `q06` | 1/4 | 0,250 | 0,100 | la campanita que se cuelga a los bebes para protegerlos |
| `q08` | 1/4 | 0,250 | 0,167 | follaje seco que cae en septiembre |
| `q10` | 1/2 | 0,500 | 0,333 | una bicicleta antigua |

### Contraste con las predicciones de la exploración

Las cinco consultas que D8 tabuló se reproducen **al decimal**:

| consulta | ingenuo predicho | ingenuo medido | corregido predicho | corregido medido |
|---|---:|---:|---:|---:|
| `sortija de plata` | 2/3 = 0,67 | **2/3 = 0,67** | 2/2 = 1,00 | **2/2 = 1,00** |
| `bano de oro` | 1/1 = 1,00 | **1/1 = 1,00** | 1/1 = 1,00 | **1/1 = 1,00** |
| `gargantilla dorada` | 1/1 = 1,00 | **1/1 = 1,00** | 1/1 = 1,00 | **1/1 = 1,00** |
| `una bicicleta antigua` | 1/3 = 0,33 | **1/3 = 0,33** | 1/2 = 0,50 | **1/2 = 0,50** |
| `follaje seco…` | 1/6 = 0,17 | **1/6 = 0,17** | 1/4 = 0,25 | **1/4 = 0,25** |

La exploración calculó esto ejecutando `expand_query` + `counting_flags` sin base; la comprobación
de `numnode` contra PostgreSQL confirma que la aritmética era correcta.

---

## M3 · Hermanas de familia en el top-10 — la penalización de variante, refutada con cifra

Cruzando los `ranked` de `v2-hibrido` del run `d9222333` con `ai.product_document.family_id`, para
las 48 consultas juzgadas. Se cuenta, por consulta, **cuántos miembros de la familia más repetida**
aparecen en el top-10.

| hermanas de la familia más repetida | consultas | % |
|---:|---:|---:|
| 0 | 10 | 20,8 % |
| 1 | 13 | 27,1 % |
| 2 | 11 | 22,9 % |
| 3 | 7 | 14,6 % |
| **4** | 7 | 14,6 % |
| **5 o más** | **0** | **0,0 %** |

- Consultas con **3+** hermanas en el top-10: **14 de 48 (29,2 %)**
- Consultas con **4+**: 7 de 48 (14,6 %)
- Huecos del top-10 ocupados por la familia más repetida, en media: **1,75 de 10**

**La condición que D16 se puso a sí mismo se cumple en las dos direcciones.** Por un lado el techo
es real y bajo: **ninguna consulta pasa de 4 hermanas**, coherente con el reparto de familias que
midió C18a (sólo 2 de 156 familias tienen 5 o más miembros). En el peor caso la familia ocupa 4 de
los 10 huecos que el operador ve, y quedan 6. La inundación que la ficha temía **no existe**.

Por otro, el 29,2 % **no es despreciable**: en casi un tercio de las consultas hay tres o más
hermanas compitiendo por la atención. D16 previó exactamente este resultado y dejó escrita su
consecuencia: **la respuesta sigue siendo presentación, y `groups[]` sube de prioridad en C30/C36.**
Penalizar seguiría costando relevancia —sin talla nombrada las hermanas son legítimamente grado 2—
y seguiría escondiendo al operador que las tallas existen.

**`test_ambiguous_variant_penalty_applies_only_within_family` queda refutado con una cifra y no por
argumento**, que era la condición para no repetir el error que este proyecto ya cometió una vez. C25
no toca familias.

---

## M4 · El reparto de los buckets — el binario, confirmado con cifra

Sobre los **6.050** pares asignados de `ai.pos_projection`:

| `qty_bucket` | pares | % del total |
|---|---:|---:|
| `0` | 428 | 7,07 % |
| `1-2` | **191** | **3,16 %** |
| `3+` | 5.431 | 89,77 % |

De los **5.622** pares no nulos, `1-2` es el **3,4 %** y `3+` el **96,6 %**.

**El MUST heredado pasa de conservado por inercia a respaldado por una cifra.** D17 lo refutaba por
construcción —con `g_efectivo` los dos buckets caen en la misma rama, ninguno pierde grado, y no
existe función objetivo que pueda ordenarlos—. La medición añade el argumento independiente: aunque
existiera esa función, **calibraría sobre el 3,2 % de los pares**. Una perilla ajustada sobre 191
filas de 6.050, con una lectura de negocio de signo ambiguo, se ajustaría al ruido.

Confirmado también, exactamente como lo dejó C22: **1.424 de 6.050 pares asignados (23,54 %)** tienen
`sales_30d > 0`. Es la densidad sobre la que la rotación sería un desempate — y la razón, junto con
la ausencia de gancho en la rúbrica, de que D10 la declare en vez de calibrarla.

---

## Fase A · El barrido de la fusión, y lo que decide (tareas 9.1 y 9.2)

32 puntos: 8 valores de `rho` x 2 pares `(k, profundidad)` x 2 reglas de cobertura. Tabla
completa en [`c25-sweep-fase-a.md`](../../../ai-service/evals/results/c25-sweep-fase-a.md).

### El veredicto: el default NO se mueve

| | `rho` | k/prof. | cobertura | global | ajuste | **nuevas (decide)** |
|---|---:|---:|---|---:|---:|---:|
| **vigente** | 1,0 | 60/60 | continua | 0,663 | 0,936 | **0,608** |
| mejor del barrido | 0,6 | 40/40 | continua | 0,669 | 0,932 | **0,616** |

**+0,008 en la lectura que decide, muy por debajo del margen de 0,05.** Con un intervalo de
±0,13 sobre la porción real, esa diferencia no se distingue del ruido de anotación. El arranque
`rho = 1,0` —valor **de principio**, no ajustado: *cada rama tiene un voto*— se conserva.

**Ojo con no leer mal este «no se mueve».** Es sobre mover el default **dentro** de la rejilla de
`v2b`. Contra la línea base publicada, que es lo que el change tiene que batir, la fusión por rama
gana **+0,073** en `nuevas` (0,608 contra 0,535 de `v2-hibrido`), muy por encima del margen.

### La superficie es plana, y eso también es un resultado

Las 32 lecturas de `nuevas` caen entre **0,605 y 0,616**: once milésimas de recorrido en toda la
rejilla. La explicación está en la regla adaptativa: con cobertura parcial ya reduce `w_lex` por
su cuenta, así que el cociente **efectivo** se despega del nominal y el valor global de `rho`
decide poco. La banda estrecha que la exploración predijo sigue siendo real —gobierna el caso de
cobertura 1,00— pero deja de gobernar el agregado.

### M7 · El brazo de control: ¿aporta algo la regla adaptativa?

El barrido de 9.1 comparaba **dos formas de la misma idea** y no podía decir si la idea vale.
Faltaba el **control**: la fusión por rama con la regla **apagada**. Añadido y medido.

**Por categoría, con `rho = 1,0`:**

| categoría | n | **control** (sin regla) | con adaptativa | delta |
|---|---:|---:|---:|---:|
| `descripcion-sin-anclaje` | 12 | 0,289 | **0,417** | **+0,128** |
| `subjetiva` | 5 | 0,682 | 0,682 | **+0,000** |
| `piedra` | 4 | 0,747 | 0,747 | **+0,000** |
| `variante-talla` | 7 | 0,830 | 0,830 | **+0,000** |
| `materiales` | 5 | 0,959 | 0,959 | **+0,000** |
| `sinonimos` | 6 | 0,969 | 0,969 | **+0,000** |
| `lexico-exacto` | 4 | 1,000 | 1,000 | **+0,000** |
| `fuera-de-dominio` | 5 | 0,000 | 0,000 | +0,000 |
| **`new` (decide)** | 40 | 0,571 | **0,608** | **+0,037** |

**La predicción falsable de D7 se cumple exactamente, y de punta a punta sobre el índice vivo.**
La regla aporta **+0,128** donde fue diseñada para aportar y **cero exacto** en las otras siete
categorías. No es que el daño sea pequeño: es **cero**, en las cinco de cobertura 1,00 y también
en las dos que no lo son. El gate de la tarea 4.4 lo afirmaba estructuralmente sobre un doble;
esto lo confirma contra la base.

### M8 · Por qué la superficie es plana: la regla absorbe el filo del cuchillo

La misma rejilla de `rho`, con la regla apagada y encendida, en la lectura que decide:

| `rho` | **control** (sin regla) | con adaptativa |
|---:|---:|---:|
| 0,6 | 0,540 | **0,613** |
| 0,8 | 0,536 | 0,609 |
| 0,9 | 0,536 | 0,608 |
| 0,95 | 0,554 | 0,608 |
| 1,0 | 0,571 | 0,608 |
| 1,05 | 0,603 | 0,608 |
| 1,1 | **0,606** | 0,606 |
| 1,25 | 0,605 | 0,605 |
| **recorrido** | **0,070** | **0,007** |

**Sin la regla, `rho` es un acantilado**; con ella, una meseta. El control reproduce exactamente
el cruce que la exploración predijo: por debajo de 0,95 la rama vectorial no alcanza el top-5, por
encima de 1,05 sí, y entre medias hay **siete centésimas** de caída. Es el «filo de cuchillo» que
C24 describió, medido.

Y hay más: **la adaptativa está por encima del máximo del control en casi todo el recorrido**. Lo
mejor que consigue afinar `rho` a mano es **0,606**; la adaptativa da 0,608 en el arranque de
principio y 0,613 en su mejor punto. **No es equivalente a ajustar `rho`: es mejor, y llega sin
ajustar nada.**

La razón es que `rho` es una constante **global** y la cobertura es **por consulta**. Subir `rho`
ayuda a las consultas sin anclaje y paga en las ancladas —lo que C24 midió como `sinonimos`
−0,039 y `materiales` −0,010—; la adaptativa sube el cociente **efectivo** sólo donde hace falta.
La tabla por categoría de M7 es esa frase convertida en cifra.

**Consecuencia de ingeniería, y es la que más vale:** un default que se apoya en un acantilado
está a un `ANALYZE` de distancia de ser el equivocado. La regla adaptativa convierte `rho` en una
elección robusta, y ésa es una propiedad que ninguna cifra de nDCG agregada deja ver.

### La variante binaria no es distinguible, y eso NO es una confirmación

Las 16 filas `binary` salen **idénticas** a las 16 `continuous`, hasta el último decimal. No es
que la perilla no llegue: el log lo desmiente —`coverage=0,250` da `w_lex_effective` **0,1250**
con la continua y **0,2500** con la binaria—. Son dos razones independientes:

1. **`α = 0,5` coincide con la cobertura parcial más frecuente.** Medidas sobre el golden set, las
   coberturas son casi todas **1,00 o 0,50**, y en 0,50 la binaria da `w_lex x 0,5`, que es
   **exactamente** lo que da la continua. La elección de `α` fue desafortunada por construcción.
2. **Donde sí difieren, las dos saturan.** En `q08` la continua deja el cociente efectivo en 4,0 y
   la binaria en 2,0; el orden de la fusión satura por encima de ~1,1, así que el top-5 es el
   mismo. Comprobado además con `α = 0,1`, que da cociente 10,0 y el mismo top-5.

**Consecuencia honesta:** la segunda fila candidata **no puede falsar** la elección en este
conjunto. La regla continua se adopta por su propio mérito —**cero parámetros**, la propiedad que
D7 invocó— y no por haber ganado una comparación que la medición no puede resolver. El intento de
falsación queda registrado como **no concluyente**, que es distinto de un aval.

## Fase A · El umbral NO se re-fija aquí (tarea 9.3)

Registrado explícitamente porque su ausencia sería indistinguible de un olvido. **M1 asignó el
trabajo del umbral a la fase D**, así que la fase A no toca `JPV_RETRIEVAL_DISTANCE_THRESHOLD` y
**el conjunto de candidatos no se altera por ningún cambio de umbral**.

Lo que sí mueve la ventana en esta fase es la fusión: `rho`, `k` y la profundidad deciden qué
entra. Por eso la captura de la fase B se toma **después** de congelar la fusión, y no antes.

Si M1 hubiera salido al revés —un escalar que separase las dos poblaciones— este apartado
registraría el umbral nuevo y la advertencia de que invalida cualquier ventana capturada. No es
el caso: el umbral sigue en **0,65**, exactamente donde C14 lo dejó.

## M5 · La rotación, retirada del orden por medición

**Medición no planificada**, ejecutada durante el apply cuando el barrido de la fase C mostró que
la rotación pagaba en las dos lecturas. D10 la había fijado como *desempate declarado, no
calibrado*, con peso 0,25. La medición la retira del orden.

### El requisito, tomado al pie de la letra, es un no-op

La spec exigía que la rotación *«SHALL act as the last ordering key, deciding only between
candidates that the fusion and the availability signal rank equally»*. Empates exactos de score
hay, y muchos: **662 pares, el 35,1 %** de los 3.774 candidatos de las 48 ventanas — RRF los
produce porque `w/(k+1) + w/(k+2)` iguala a `w/(k+2) + w/(k+1)`. Pero de los que caen **dentro del
top-5**, los que enfrentan a un vendedor con un no-vendedor son:

> **0 pares en las 48 consultas.**

Implementada como su propio requisito la define, la rotación nunca actúa y su peso no puede
importar.

### Como clave de ordenación no desempata: particiona

| | |
|---|---:|
| pares cuyo orden relativo invierte | **11.067** |
| adyacentes en la fusión (empate real) | **3,4 %** |
| separados por **más de 10 puestos** | **71,2 %** |
| salto mediano | **21 posiciones** |
| salto máximo | 98 posiciones |

Es estructural: un indicador binario al final de una clave lexicográfica **parte el bloque entero
en dos**. Como **168 de los 416** productos que MAO-AIR lleva vendieron algo, la rotación partía
la lista casi por la mitad y reordenaba a través de todo el orden de fusión.

### Y donde actúa, cuesta

De las **22** entradas nuevas al top-5 que provoca, **6 desplazan a un documento de mejor grado**.
En agregado paga en las dos lecturas:

| | relevancia pura (`new`) | operativa |
|---|---:|---:|
| sólo disponibilidad | **0,595** | **0,656** |
| con rotación | 0,584 | 0,645 |

La señal además es gruesa: **7 valores distintos, máximo 6**, y el **64,5 %** son cero.

*Hipótesis descartada por el camino:* que la rotación fuera un proxy de «pieza barata» y
degradara sistemáticamente el inventario caro. Es al revés — lo que vende es **más caro**
(538,13 € de media frente a 415,22 €; mediana 385 € frente a 275 €).

### Veredicto

**Un mecanismo que sólo puede ser un no-op o un error no se ajusta: se retira.** La frase que lo
justificaba sigue siendo cierta en el mostrador; lo que la medición establece es que este
recuperador no produce la situación que la frase describe. `sales_30d` se sigue leyendo y
persistiendo para publicar su distribución y para C26, y la prohibición de ordenar con ella
vuelve a ser **estructural**: el protocolo que lee la ordenación no tiene el campo.

El modelo de negocio queda en **un peso y una frase**: *una pieza de la que la tienda se ha
quedado sin existencias se enseña después de las piezas comparables que sí tiene.*

## M6 · El peso de disponibilidad decide su signo, no su valor

Siete puntos de rejilla sobre el peso de disponibilidad —0,25, 0,5, 0,75, 1,0, 1,5, 2,0— dan
**cifras idénticas hasta el último decimal**. Sólo el cero difiere.

Es aritmética, no ruido: con un único término binario el score toma **dos valores**, y como es la
última clave lexicográfica, el orden depende de cuáles son mayores, no de cuánto. La calibración
decide **encender o apagar**, y `1,0` es una **unidad declarada**.

Publicarlo así importa: un «peso calibrado» que no calibra nada afirma una evidencia que nunca se
produjo. La spec recoge ahora la obligación de declararlo.

## Qué queda decidido al cerrar la fase 0

1. **La abstención es una regla relativa por consulta y vive en la fase D.** No mueve la ventana.
   Las ventanas de la fase B valen para toda la fase C.
2. **El denominador de la cobertura se calcula con `numnode > 0`**, y el gate de la tarea 4.4 cubre
   **cinco** categorías, no cuatro: se añade `variante-talla`.
3. **La penalización de variante no se implementa.** Refutada con 29,2 % y techo de 4.
4. **El binario de `qty_bucket` no se calibra.** Refutado con 3,4 %.
5. **La rotación no ordena nada.** Refutada con 0 pares del top-5 y 11.067 inversiones (M5).
6. **El peso de disponibilidad decide su signo, no su valor.** Invariante en siete puntos (M6).

Ninguna de las cuatro decisiones se ha tomado mirando el resultado de un barrido, porque **todavía no
se ha ejecutado ningún barrido**.
