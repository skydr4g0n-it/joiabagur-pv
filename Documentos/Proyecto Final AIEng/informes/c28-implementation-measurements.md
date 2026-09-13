# C28 — Informe de implementación: la revisión humana de perfiles, y los dos números que produce

**Change:** `add-profile-review-ui-and-metrics` · **Rama:** `c28-add-profile-review-ui-and-metrics`
**Sesión de revisión:** 2026-09-13 · **Semilla del muestreo:** `c28-profile-review`
**Revisor:** único, y es además quien diseñó el muestreo — declarado en §9
**Exploración previa:** [c28-exploration-measurements.md](c28-exploration-measurements.md)

El §16 del diseño pedía dos cifras que hasta hoy no existían: los 1.200 perfiles estaban en
`ReviewOrigin = AutoBulk` con **cero revisores y cero tiempos**. Este informe las entrega, dice qué
significan exactamente, y declara las tres cosas que la sesión **no** pudo medir.

---

## 1. Lo que la sesión produjo

```sql
SELECT count(*), count("ReviewDurationMs"), round(sum("ReviewDurationMs")/60000.0,0)
FROM "ProductAiProfiles" WHERE "ReviewOrigin" = 2;
```

| | |
|---|---|
| Perfiles revisados por una persona | **204** |
| De ellos, **cronometrados** | **204 (100 %)** |
| Duración total de la sesión | **109 minutos** |
| Aprobados / rechazados | 203 / 1 |
| Cuota de diseño | 180 (60 por estrato) |

**El 100 % de cronometrados es el resultado que más costó.** C18b registró **6 tiempos de 64
juicios** porque su cronómetro vivía en el estado del componente y moría con la pestaña. Aquí el
tiempo viaja en la misma petición que registra el juicio, y un test lo exige
(`Review_IndividualWithoutDuration_IsRejected`). La media de aquel entregable no existe; ésta sí.

### Reparto por estrato

| estrato | corpus | revisados | cuota | tasa de muestreo |
|---|---:|---:|---:|---:|
| **A** · ausencia de evidencia | 122 | 70 | 60 | 57 % |
| **B** · afirmado sin frase en el texto | 285 | 69 | 60 | 24 % |
| **C** · afirmado con frase en el texto | 761 | 65 | 60 | 8,5 % |
| | **1.168** | **204** | 180 | 17,5 % |

Se superó la cuota en los tres estratos. **No fue deliberado:** la cola se dibuja sobre
`ReviewOrigin = AutoBulk`, así que revisar un perfil lo saca del universo y otro ocupa su sitio —
la cola **no se acaba**, avanza. El contador de cabecera muestra el progreso contra la cuota pero
no bloquea, y el revisor esperaba que parase solo. Es un hallazgo de interfaz, anotado en §8.

Las celdas desiguales no invalidan nada: el total va ponderado por el tamaño real de cada estrato
en el corpus, precisamente porque las tasas de muestreo son deliberadamente distintas.

---

## 2. Los dos números del §16

| | |
|---|---|
| **Tasa de corrección, ponderada por el catálogo** | **20,9 %** |
| **Tiempo medio por ítem** | **32,1 s** (n = 204, todos cronometrados) |

Sobre la muestra sin ponderar la tasa es del 24,1 % — 344 correcciones de 1.428 juicios de campo.
La diferencia entre ambas es el efecto del diseño estratificado: el estrato A está sobremuestreado
siete veces respecto a C, así que la cifra de la muestra describe la muestra y no el catálogo.

### Pero el número de titular hay que partirlo en dos

| grupo | corregidos / juicios | tasa |
|---|---:|---:|
| **Campos sensibles** (`piece_type`, `materials`, `stone_type`, `size_label`) | 85 / 816 | **10,4 %** |
| **Etiquetas comerciales** (`color_tags`, `style_tags`, `occasion_tags`) | 259 / 612 | **42,3 %** |

Las tres etiquetas aportan **el 75 % de todas las correcciones**, y no miden lo mismo. El revisor
lo dijo con precisión al terminar:

> *«Las adiciones están casi todas en los tags porque normalmente siempre venían vacías. Es algo
> subjetivo y que yo he ido rellenando con mi criterio.»*

Esa frase es la interpretación correcta del 42,3 %: no es *«el extractor se equivocó en el 42 % de
las etiquetas»*, es *«el extractor no propuso etiqueta y una persona opinó una»*. No hay verdad de
referencia contra la que contrastar una opinión de estilo u ocasión, y el criterio declarado de la
revisión —fidelidad al texto de origen— apenas restringe qué estilo tiene una pieza.

**Por eso la cifra que el §16 debe citar es el 10,4 % de los campos sensibles**, que son los que el
diseño define como aquellos cuyo error llega a un cliente, y los únicos donde el texto de origen
decide la respuesta. El 20,9 % ponderado se publica junto a él, con esta descomposición al lado y
nunca sin ella.

### Por campo

| campo | corregidos / 204 | tasa ponderada | lectura |
|---|---:|---:|---|
| `piece_type` | 1 | **0,3 %** | el vocabulario cerrado funciona |
| `size_label` | 1 | 1 % | 100 % producido por regla |
| `stone_type` | 35 | 8,1 % | |
| `materials` | 48 | 9,5 % | |
| `color_tags` | 47 | 23,1 % | subjetivo |
| `occasion_tags` | 106 | 52 % | subjetivo |
| `style_tags` | 106 | **52,8 %** | subjetivo |

**`piece_type` con una corrección de 204 es el resultado silencioso de la sesión.** Es el campo con
filtro por igualdad estricta (`AND d.piece_type = :category`), el más caro de equivocar, y el
extractor acierta prácticamente siempre. Es también el vocabulario que `FIX1` amplió, lo que sugiere
que aquella ampliación hizo su trabajo.

---

## 3. La predicción falsable del diseño: confirmada a medias

El diseño (D5) predijo que **las retiradas se concentrarían en el estrato B** —donde el modelo
afirma sin frase que lo respalde— **y las adiciones en el C**. Sobre los campos sensibles, que es
donde se hizo la predicción:

| estrato | juicios | adiciones | **retiradas** | sustituciones | tasa |
|---|---:|---:|---:|---:|---:|
| A | 280 | 51 | **0** | 13 | 22,9 % |
| B | 276 | 0 | **8** | 10 | 6,5 % |
| C | 260 | 1 | **1** | 1 | **1,2 %** |

**✅ La mitad de las retiradas se confirma, y limpiamente.** Ocho de las nueve retiradas de campos
sensibles están en B, y B es el único estrato con retiradas: cero en A, una en C. La hipótesis era
que el estrato «afirmado sin evidencia textual» concentraría las alucinaciones, y eso es
exactamente lo que ocurrió.

**❌ La mitad de las adiciones se refuta.** Las adiciones están en A (51), no en C (1). Visto ahora
es obvio y el diseño no lo vio: el estrato A **es** el de los campos vacíos, así que rellenar uno
*es* una adición por construcción. Predecir adiciones en C mientras se define A como «ausencia» era
incoherente, y ninguna de las revisiones del diseño lo detectó.

### El span sirve como triaje, y ésa es la respuesta a la pregunta del diseño

**1,2 % de corrección en el estrato C sobre campos sensibles.** Si un valor tiene su frase
literalmente en el texto de origen, es casi seguro correcto. Frente al 22,9 % de A y el 6,5 % de B,
el escalón es grande y ordena bien.

**Pero esto no puede leerse como que el span sea un buen filtro de calidad**, y la razón está en la
sección siguiente.

---

## 4. Lo que la sesión NO pudo medir, y hay que decirlo

### 4.1 — La afirmación central de la exploración queda abierta

La exploración midió que **94 productos nombran un material que el extractor no extrajo**, 81 de
ellos en el estrato de máxima confianza, y de ahí salió la tesis que gobierna todo el diseño del
muestreo: *«la heurística de span solo caza falsos positivos; es ciega, por construcción, a las
omisiones»*.

La sesión encontró **1 adición en el estrato C**. Eso admite dos lecturas opuestas, y **los datos no
permiten elegir**:

```sql
-- candidatos a omisión (hilo/perla en el texto, no extraídos) que quedan en el estrato C
   total: 28     ya revisados por la sesión: 2
```

Con 65 de 761 muestreados (8,5 %), tocar 2 de 28 candidatos es exactamente lo esperable por azar.
**La prueba no se ejecutó.** En los dos que sí se revisaron el revisor no añadió el material, lo que
apunta en la dirección de la cautela que la propia exploración se puso —`hilo` aparece a menudo como
técnica («hilo de plata») y no como material— pero con n = 2 eso no es un resultado.

**Consecuencia:** el 1,2 % del estrato C es una tasa correcta sobre una muestra aleatoria de C, y
**no** es evidencia de que no haya omisiones. Cerrar esa pregunta pide una pasada dirigida sobre los
28 candidatos, reportada aparte y **fuera** de la tasa estratificada, porque una muestra dirigida no
es una muestra.

### 4.2 — El A/B de teclado no se obtuvo, pero el teclado sí se probó

La tarea 10.3 pedía revisar los ~140 últimos ítems con teclado en bloque, para compararlos con los
~40 primeros a ratón. **Los bloques no se separaron.** El revisor usó los atajos, no percibió
ventaja, y acabó volviendo al ratón por defecto:

> *«No he encontrado diferencia entre usar el ratón o el camino rápido con el teclado, no aporta
> mucho el teclado.»*
>
> *«El teclado sí se usó, pero aporta poco o nada a la revisión.»*

**Esa distinción importa y conviene no comprimirla.** Hay dos afirmaciones separadas:

- **El A/B no existe.** Con ambos modos entremezclados no hay dos poblaciones que comparar, y
  ninguna partición de los tiempos mide la interfaz.
- **Pero el requisito de teclado sí tiene la prueba que su spec pide.** El requisito de
  `family-review` fue escrito precisamente porque C18b lo dio por entregado sin handler alguno, y
  dice que *«la prueba que importa es una cola trabajada de principio a fin con ellos, no que haya
  un manejador enganchado»*. Una persona los usó sobre la cola real. **Lo que la sesión añade es un
  veredicto sobre su utilidad, que es un resultado y no una casilla**: los atajos funcionan y no
  aportan tiempo apreciable en esta tarea, probablemente porque el cuello de botella es leer la
  descripción y decidir, no desplazar la mano.

Los tiempos por bloques de 25 ítems son éstos:

```
   1- 25    66,9 s        101-125    21,7 s
  26- 50    31,3 s        126-150    22,1 s
  51- 75    51,8 s  ←     151-175    20,8 s
  76-100    23,6 s        176-200    21,0 s
```

La tentación es publicar «ratón 49,1 s → teclado 26,6 s, un 46 % más rápido». **Sería falso**: los
dos bloques se hicieron con ratón, así que esa diferencia es **curva de aprendizaje**, no interfaz.
El pico de 51,8 s en los ítems 51-75 tampoco es un dato de la revisión: es el tramo en el que la
sesión se interrumpió varias veces para corregir defectos de la pantalla (§8), y el cronómetro corre
mientras el ítem está abierto.

Lo que sí se puede afirmar es el **régimen estable de una persona entrenada: ~21 s por ítem** a
partir del ítem 100, con ambos modos disponibles. Los atajos quedan implementados, probados y
**usados**, lo que retira la afirmación falsa que C18b dejó archivada en su tarea 6.4 — pero **su
efecto sobre el tiempo no está medido**, y estimarlo sería inventarlo.

### 4.3 — Las 22 filas de `enrichment/v2` siguen sin ser una comparación

El corpus tiene **1.178 perfiles en `enrichment/v1` y 22 en `v2`** (los de `FIX1`, todos sintéticos).
El plan obliga a reportar por versión de prompt para no mezclar poblaciones, y así se reporta; pero
22 filas siguen siendo una nota al pie y el §11.6 no debe venderse con esto.

---

## 5. Huecos de vocabulario: el hallazgo con ruta propia

Ésta es la sección que el revisor pidió destacar, y tiene razón: es lo más accionable que produjo la
sesión.

### 5.1 — De dónde salió

Apareció en **el primer ítem del lote**. El `Broche Calor Ancestral L` (SKU458) dice en su texto
*«forjado en platino… rodeado de filigranas de cobre»*, y su campo `materials` venía vacío. **Estaba
bien vacío**: `platino` y `cobre` no están en el vocabulario cerrado de nueve términos. El extractor
no falló; el vocabulario no llega.

Eso obligó a una decisión de diseño a mitad de sesión, porque escribir `platino` a mano habría hecho
dos destrozos a la vez:

1. **El valor sería inencontrable.** `materials && ARRAY[…]` es un test de solapamiento contra los
   nueve canónicos que el buscador ofrece; un décimo término no lo nombra ninguna consulta.
2. **Contaminaría la métrica.** Se contaría como adición, reportando la cobertura del vocabulario
   como error del extractor. Son defectos distintos con remedios distintos.

La pantalla pasó a ofrecer los seis campos de vocabulario cerrado como selección, con `size_label`
en texto libre (§8.2), y los términos ausentes se anotan como **hallazgo**, explícitamente fuera de
la tasa.

### 5.2 — Lo que la sesión registró

**28 anotaciones sobre 13 términos**, repartidas en tres campos. La tercera columna es lo que la
sesión vio; la cuarta es lo que hay en el catálogo entero, medido después con el mismo criterio de
palabra completa:

| campo | término ausente | en la muestra (204) | **en el corpus (1.200)** |
|---|---|---:|---:|
| `materials` | `vidrio` | 13 | **67** |
| `style_tags` | `naturaleza` | 8 | **38** |
| `materials` | `platino` | 11 | 20 |
| `materials` | `cobre` | 9 | 15 |
| `stone_type` | `cuarzo rosa` | 1 | 7 |
| `stone_type` | `turmalina` | 1 | 5 |
| `materials` | `titanio` | 2 | 5 |
| `materials` | `bronce` | 2 | 3 |
| `materials` | `marfil` | 2 | 2 |
| `materials` | `hierro` | 1 | 2 |
| `materials` | `madera` | 1 | 1 |
| `materials` | `nácar` | 1 | — *(ver abajo)* |

**`vidrio` es el hallazgo grande, y no lo sospechaba nadie.** Alcanza **67 productos, el 5,6 % del
catálogo**, y la exploración no podía verlo: solo buscó los términos que ya estaban en el
vocabulario (`hilo`, `perla`, `plata`, `acero`, `latón`). Un hueco de cobertura es invisible para
una consulta que solo sabe preguntar por lo que ya conoce. **Hacía falta una persona leyendo.**

**El mecanismo de registro funcionó.** La sesión anotó 13 de los 67 `vidrio` (19 %) revisando el
17 % del catálogo: el revisor marcó prácticamente todos los que se le pusieron delante. `platino`
sale por encima de lo esperable (11 de 20) porque el revisor iba avisado de ese caso concreto.

**Tres clases de hallazgo que conviene no mezclar:**

- **Cobertura** — el término no existe en ningún vocabulario: `vidrio`, `platino`, `cobre`,
  `titanio`, `bronce`, `madera`, `marfil`, `hierro`, `turmalina`, `naturaleza`. Son los que piden
  ampliar la lista.
- **Granularidad** — `cuarzo rosa`, cuando `cuarzo` **sí** está en `stone_type`. La ficha de
  conocimiento ya lo describe: *«El cuarzo cristalino da el cristal de roca incoloro, el ahumado y
  el rosa»*. No falta el término; falta el matiz, y ampliarlo tiene un coste distinto.
- **Frontera de campo** — `nácar` anotado como hueco de `materials`, cuando `nacar` **está en el
  vocabulario de `stone_type`**. No es un hueco: es la pregunta de si el nácar es el material del
  que está hecha la pieza o la piedra que lleva engastada. Es una decisión de modelado, no de
  cobertura.

*(`marfil` aparecía dos veces en la exportación, una de ellas como `marfll`. Fusionado aquí.)*

**`naturaleza` abre el segundo hueco conocido de `style_tags`.** El primero es `filigrana`, que
`FIX1` dejó declarado en `DEFERRED_TASKS.md` y que alcanza 66 documentos por sí solo. Con 38 más de
`naturaleza`, ese eje empieza a tener un caso propio — y el registro de FIX1 ya avisó de que
`style_tags` *«es otro eje con sus propias puertas de cobertura en el auditor»*, así que no es el
mismo change que ampliar `materials`.

### 5.3 — La alucinación que la confianza ya cazaba

Midiendo `platino` antes de la sesión apareció un patrón que merece publicarse por sí solo. De los
**20 productos cuyo texto dice `platino` y ninguno dice `plata`**:

| qué extrajo el modelo | productos | confianza | estrato |
|---|---:|---|---|
| `["plata"]` o `["oro","plata"]` | **11** | 0,45 | B |
| `[]` | 9 | 0,20 | A |

Los once son una alucinación de manual: el modelo lee «platino», no lo encuentra entre los nueve
canónicos y emite el metal más parecido que conoce. **El sistema de confianza los cazó a los once**
— 0,45 significa literalmente *«lo afirmó sin que la frase esté en el texto»*— y los depositó en el
estrato B, que es donde la sesión encontró sus ocho retiradas. Es la confirmación del mecanismo, no
solo del número.

`cobre` aparece en 15 productos, los 15 en el estrato A.

### 5.4 — La ruta de ampliación, y por qué no cabía aquí

Ampliar el vocabulario **cambiaría el lote a mitad de medición**, y ahora se puede cuantificar.
`confidence.py` calcula el span contra el vocabulario, así que un término nuevo que aparezca en el
texto sube la confianza de ese campo de `0,20` o `0,45` a `0,85` — y con ella, el estrato. Los tres
términos grandes están repartidos así sobre los 1.167 perfiles aprobados:

| término | A | B | C |
|---|---:|---:|---:|
| `vidrio` | 1 | **19** | 47 |
| `platino` + `cobre` | **20** | **11** | 0 |

Añadir los tres sacaría del estrato A **21 de sus 122 productos (17 %)** y del B **unos 30 de 284
(11 %)**. Los 180 dejarían de ser los 180 que produjeron la cifra de este informe, y el estrato A
—el más caro de llenar, con solo 122 productos— se quedaría más corto todavía.

Y obliga a re-enriquecer, que reescribe `ProposedProfileJson`: la columna contra la que se mide la
tasa de corrección.

Lo que costaría, completo:

1. Los términos en `vocabularies.yaml`, **por campo y no todos juntos**: `materials` y `stone_type`
   son un change; `style_tags` es otro, porque `FIX1` ya dejó escrito que ese eje *«tiene sus
   propias puertas de cobertura en el auditor»*.
2. Una ficha de conocimiento **por cada material canónico nuevo** — `material-vidrio.md`,
   `material-platino.md`, `material-cobre.md`… **No son opcionales:** la spec viva de
   `knowledge-corpus` exige exactamente una por término, y
   `test_every_canonical_material_has_exactly_one_sheet` falla nombrando el que falte. Las piedras
   van por otro camino: el mismo requisito dice que una piedra sin producto en catálogo no lleva
   ficha propia, así que `turmalina` sería una sección en `piedras-cuarzos-y-gemas-facetadas.md`.
3. Reindexar el corpus de conocimiento.
4. Re-enriquecer con versión de prompt nueva, como `FIX1` hizo con sus 22 productos en
   `enrichment/v2`.

**Orden obligatorio:** este informe tiene que estar publicado antes. Re-enriquecer primero mezcla
dos poblaciones y ninguna de las dos cifras significa lo que dice.

**Cautela heredada:** igual que con `hilo`, *«baño de platino»* o *«filigranas de cobre»* no son
necesariamente una pieza **de** platino o **de** cobre. Por eso el registro guarda el SKU además del
término: el change que amplíe la lista mira los textos reales antes de decidir.

---

## 6. Los 32 rechazados, y la pregunta 5 del ticket

Se revisaron con la pregunta invertida —*¿hay algún rechazo incorrecto?*— y el veredicto del revisor
fue que **ninguno lo era**. Ningún perfil volvió a `Approved`.

Eso **resuelve la pregunta abierta 5 del ticket en contra de lo que la exploración sospechaba**. La
exploración señaló `Presión Oro` (`piece_type: anillo`, `materials: ["oro"]`) como *«una sortija
vendible que ha quedado fuera del índice»* y le dio valor comercial. La revisión humana dice que no.
Los 32 son lo que la exploración describió en conjunto: la tienda de regalos —velas, palo santo,
cajas, postales, imanes, llaveros— y el rechazo es correcto.

---

## 7. Estado final del corpus

| `ReviewStatus` | `ReviewOrigin` | perfiles |
|---|---|---:|
| `Approved` | `AutoBulk` | 964 |
| `Approved` | `Human` | **203** |
| `Rejected` | `AutoBulk` | 32 |
| `Rejected` | `Human` | **1** |

El índice se movió en una sola fila: el perfil que una persona rechazó sale del feed, que selecciona
`product.IsActive && profile.ReviewStatus == Approved`. Los 203 aprobados siguen indexados y los
corregidos se reemiten solos, porque `IndexFeedRepository` incluye `profile.UpdatedAt` en la marca de
agua.

**Porcentaje del corpus revisado por una persona: 17,0 %** (204 de 1.200). Éste es el número que
corrige la limitación 2 del §15 del diseño.

---

## 8. Lo que la sesión obligó a corregir en la propia pantalla

Cuatro defectos que solo aparecieron revisando de verdad. Tres los encontró el revisor.

### 8.1 — La cola se agotaba en la primera página

Tras aprobar los 50 de la primera página la pantalla se quedaba seca, aparentando el final del lote
con 130 ítems por delante. El servidor estaba bien; la pantalla no volvía a pedir la cola. Ahora el
perfil juzgado desaparece en el acto y la página siguiente se pide al agotarse la actual.

Al arreglarlo cayó un segundo defecto que solo vio el test: leer cuántos quedaban desde dentro del
actualizador de `setQueue` es una carrera, porque React no promete ejecutarlo síncrono — reportaba
página vacía, refrescaba, y devolvía al revisor al ítem que acababa de juzgar.

### 8.2 — Los campos de vocabulario cerrado admitían texto libre

Resuelto como describe §5.1. La decisión de **dejar `size_label` en texto libre** contradice lo que
parecía obvio y se tomó con datos: sus 539 valores son **100 % `rule`**, y la regex emite tallas de
anillo y largos de cadena que el vocabulario nunca tuvo — **20 valores distintos en el corpus contra
12 términos**, con `05`, `17`, `40` y `2mm` entre los sobrantes. Una lista cerrada haría imposible
registrar una talla 17.

### 8.3 — La marca «pendiente de revisión» no informaba, y mentía en el 55 % de los casos

El revisor cuestionó que tuviera sentido marcar campos como pendientes cuando el perfil entero se
revisa a la vez. La medición le dio la razón y con más fuerza que su argumento: sobre los 1.114
perfiles de la cola la marca era **constante en seis de los siete campos** —siempre encendida en
`piece_type`, `materials` y `stone_type`, siempre apagada en las tres etiquetas—. Una señal que
nunca varía no es una señal.

El séptimo variaba **porque el código mentía**: un campo sin clave en `FieldSourceJson` se rellenaba
con `inferred`, y **613 de esos 1.114 perfiles no llevan `size_label` ninguno**. Decir «inferido» a
0,20 sobre un campo que el extractor nunca propuso lo acusa de una suposición que no hizo.

La marca se retiró y la procedencia pasó a tener tres casos: `regla`, `inferido`, **`ausente`**. La
spec delta se enmendó en consecuencia —el change no estaba archivado— y la tarea 8.1, cuyo nombre
fijaba la ficha del plan, quedó tachada con su motivo. **Es la cuarta refutación de esa ficha, y la
primera que sale de usar la pantalla en vez de medir la base.**

### 8.4 — El contador de cuota no detiene la sesión

Abierto, y es el motivo de los 204 de 180. La cola avanza en vez de terminar, el contador muestra el
progreso contra la cuota pero no bloquea, y el revisor esperaba que parase solo al llegar a 60 por
estrato. No se corrigió porque se detectó al terminar. **Anotado, sin ficha.**

---

## 9. Limitaciones, declaradas

1. **Revisor único, que además diseñó el muestreo.** Exactamente como el §15 limitación 4 declara el
   etiquetador único del golden set. No hay acuerdo entre anotadores porque no hay dos anotadores.
2. **El 42,3 % de las etiquetas comerciales es subjetivo**, por declaración expresa del revisor, y no
   comparable con el 10,4 % de los campos sensibles.
3. **60 por estrato es un instrumento grueso.** Con n ≈ 65-70 el intervalo al 95 % sobre una tasa del
   0,20 es de aproximadamente ±0,10. Suficiente para separar A de C —que difieren en un factor de
   19— e insuficiente para un intervalo fino.
4. **El A/B de teclado no se obtuvo** (§4.2).
5. **La tesis de las omisiones no se puso a prueba** (§4.1).
6. **Los tiempos incluyen interrupciones.** El cronómetro corre mientras el ítem está abierto, y la
   sesión se interrumpió varias veces para corregir la pantalla. Cinco ítems superan los 2 minutos.
   La mediana (20,1 s) es más robusta que la media para el régimen estable.

---

## 10. Lo que queda anotado y sin ficha

| Hallazgo | Tamaño | Dónde |
|---|---|---|
| **`vidrio` fuera del vocabulario de `materials`** | **67 productos, 5,6 % del catálogo** | §5.2 · `DEFERRED_TASKS.md` |
| `naturaleza` fuera de `style_tags`, junto al `filigrana` de FIX1 | 38 + 66 productos | §5.2 · `DEFERRED_TASKS.md` |
| `platino` y `cobre` fuera de `materials` | 20 y 15 productos | §5 · `DEFERRED_TASKS.md` |
| Seis términos menores de `materials` y dos de `stone_type` | 1-5 productos cada uno | §5.2 |
| `StoneType` guarda una piedra y 14 productos llevan dos | 14 productos, 3,2 % | `DEFERRED_TASKS.md` |
| `cuarzo rosa`: granularidad, no cobertura | 7 productos | §5.2 |
| `nácar`: frontera entre `materials` y `stone_type` | 1 anotación | §5.2 |
| La tesis de las omisiones, sin probar | 28 candidatos, 2 revisados | §4.1 |
| El contador de cuota no detiene la sesión | — | §8.4 |
| No hay forma de volver a un perfil ya revisado | — | §8, decidido no construir |

**El primero es el que más rinde por lo que cuesta.** `vidrio` alcanza cuatro veces más productos
que `platino` y `cobre` juntos, y ninguna medición automática lo habría encontrado: la exploración
solo supo preguntar por los términos que ya estaban en la lista. Es el argumento más fuerte que deja
esta sesión a favor de que la revisión humana no es una casilla del §16 sino un instrumento.
