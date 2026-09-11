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

## Qué queda decidido al cerrar la fase 0

1. **La abstención es una regla relativa por consulta y vive en la fase D.** No mueve la ventana.
   Las ventanas de la fase B valen para toda la fase C.
2. **El denominador de la cobertura se calcula con `numnode > 0`**, y el gate de la tarea 4.4 cubre
   **cinco** categorías, no cuatro: se añade `variante-talla`.
3. **La penalización de variante no se implementa.** Refutada con 29,2 % y techo de 4.
4. **El binario de `qty_bucket` no se calibra.** Refutado con 3,4 %.

Ninguna de las cuatro decisiones se ha tomado mirando el resultado de un barrido, porque **todavía no
se ha ejecutado ningún barrido**.
