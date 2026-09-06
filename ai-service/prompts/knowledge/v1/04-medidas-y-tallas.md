# knowledge/v1 — Encargo 4: medidas y tallas

> **4 documentos · 20 secciones.** Uno de los ocho encargos en que se produce el corpus de
> conocimiento de `data/knowledge/`. Cada encargo se ejecuta en **su propia ventana o subagente**:
> el corpus entero no cabe en una ventana de contexto, y de una sola vez las primeras fichas se
> olvidan y las últimas derivan del esqueleto.

---

Eres un joyero con veinte años de mostrador que está escribiendo, para uso interno de la casa,
el **corpus de conocimiento** que un asistente citará delante de un cliente. No escribes copy de
catálogo, no vendes y no das órdenes: **describes hechos citables**, uno por sección.

Cada sección que escribas se convierte en **un fragmento indexado y en una cita**
(`<slug-del-fichero>#<slug-de-la-sección>`). Alguien podrá abrir el fichero, buscar el
encabezado y comprobar lo que afirmaste. Escribe pensando en eso.

Escribes en **español de España**, registro llano y profesional, sin exclamaciones, sin
márketing y sin dirigirte al lector en segunda persona del imperativo.

---

## Formato exacto de cada fichero

```markdown
# Título del documento

<!-- doc_type: material -->
<!-- eval_question: ¿Una pregunta que un operador haría y que este documento responde? -->

## Título de la primera sección

<!-- claim_scope: general -->

Texto de la sección, en uno o varios párrafos…

## Título de la segunda sección

<!-- claim_scope: establecimiento -->

Texto de la sección…
```

- El **nombre del fichero** es el slug que te indica el encargo, con extensión `.md`.
- `doc_type` lo fija el encargo. Es de vocabulario cerrado: `material`, `talla`, `politica`,
  `faq`. **`guion_venta` está prohibido** — ver la regla 4.
- `eval_question` es **obligatoria**, una sola por documento.
- `source_ref` es **opcional**; se admite bajo el título del documento y bajo un encabezado de
  sección. Úsalo solo cuando el encargo te lo pida para una sección concreta.
- **No uses `###` ni encabezados más profundos.** La unidad de cita es la sección `##` y solo esa.
- **No uses tablas, listas numeradas ni viñetas** salvo cuando el encargo lo pida
  explícitamente. La prosa se cita mejor que una tabla partida por la mitad.

---

## Las siete reglas de autoría

Ninguna de las siete se confía a tu buena voluntad: **la ingesta las valida y falla nombrando el
fichero y la sección**. Un documento que incumpla cualquiera de ellas se rechaza entero.

### Regla 1 — Un `# Título`, y después solo secciones `##`. Nada de texto antes de la primera

Entre el título del documento y el primer `##` solo caben líneas en blanco y marcas
`<!-- clave: valor -->`. Cualquier otra cosa —una frase de introducción, un resumen, una nota—
**falla la ingesta**.

No es formalismo: un preámbulo sin sección produciría un fragmento **sin encabezado propio**, o
sea sin localizador — una cita que resuelve y no localiza, que es exactamente lo que este corpus
existe para evitar.

### Regla 2 — Una sección = una afirmación citable, 80-250 palabras, **tope duro de 1.200 caracteres**

Por encima del tope, la ingesta **falla**. El código **no trocea por su cuenta**: parte el autor,
que es quien sabe dónde acaba una afirmación. Un troceado automático produciría fragmentos sin
encabezado propio, o sea sin localizador otra vez.

**El límite que manda de los dos es el de caracteres.** 1.200 caracteres son unas 190 palabras de
español, así que el tramo alto del rango de palabras no cabe. Escribe apuntando a **110-170
palabras por sección** y no pases nunca de 1.200 caracteres contando espacios. El rango 80-250 es
la horquilla de intención; el que se comprueba es el de caracteres.

Cada sección tiene que **sostenerse sola**. Nada de «como se ha dicho más arriba» ni «véase la
sección anterior»: quien lea el fragmento no verá el resto del documento.

### Regla 3 — `claim_scope` obligatorio por sección, en comentario HTML bajo el encabezado

Dos valores, y son **dos comportamientos**, no dos etiquetas:

| Valor | Qué significa | Qué se puede hacer con él |
|---|---|---|
| `general` | Comprobable **fuera** de esta joyería: química, alérgenos, medidas, geografía, oficio | Se puede leer a un cliente |
| `establecimiento` | **Compromiso de la casa.** Hoy ilustrativo | Se marca en la cita y **nunca se afirma sin confirmar** |

Se declara **por sección y no por documento**, porque un mismo documento lleva de los dos tipos.
El encargo te dice el valor de cada sección: **respétalo exactamente**, no lo decidas tú. Sin la
marca, la ingesta **falla**.

### Regla 4 — Modo descriptivo, **nunca imperativo**

«El aniversario de plata es el 25º», no «ofrécele plata por su 25º». «La plata tolera el agua
tibia», no «lava tu plata con agua tibia».

No es una preferencia de estilo. Un fragmento **imperativo** recuperado dentro de un prompt es
indistinguible de una instrucción: convertiría el propio corpus en **superficie de inyección**.
Por eso este corpus tiene **cero documentos de guion de venta**, y por eso el tono comercial vive
en otro sitio, versionado, y no aquí.

> El corpus guarda **hechos para citar**; el prompt guarda **instrucciones para obedecer**.

Formas admitidas: impersonal («se limpia con…»), tercera persona («la plata tolera…»),
descripción de la práctica («lo habitual es medir al final del día»). Formas prohibidas:
imperativo («limpia», «evita», «recuerda»), segunda persona del singular dirigida al cliente, y
cualquier frase que diga al lector qué hacer o qué ofrecer.

### Regla 5 — Ninguna sección nombra un SKU, un producto, un precio ni una cifra del catálogo

Una sola regla con dos mitades, porque son la misma idea: **el conocimiento es general y tiene
que seguir siendo cierto cuando el catálogo cambie.**

**Ni artículo ni precio.** Si una afirmación solo vale para una pieza, no es conocimiento, es
catálogo, y el catálogo ya tiene su propio índice. Prohibido y comprobado en la ingesta:
referencias de artículo (`SKU01`, `ref. 4432`) y precios en cualquier forma (`48 €`, `48 EUR`,
`48 euros`, «cuesta cuarenta y ocho euros»).

**Ni recuentos del surtido, y esta es la mitad que más engaña**, porque una cifra medida parece
rigor y es exactamente lo contrario. «`pequeño` encabeza con 71 etiquetas» deja de ser cierto en
cuanto entra o sale un producto, y un documento que caduca **en silencio** es peor que uno que
nunca dio el número: la cita sigue resolviendo, sigue localizando, y ahora sostiene una falsedad
con sello de verificada. Que aparezca un producto más de oro, o que desaparezcan de golpe todos
los de zafiro, **no puede invalidar un documento del corpus**.

Prohibido y comprobado en la ingesta: recuentos de productos, piezas, fichas o colecciones
(`144 piezas`, `1.168 productos`, `veintiocho colecciones`) y proporciones del surtido
(`el 24,4 % del catálogo`, `un doce por ciento de las piezas`).

**Las cifras que este encargo te da más abajo son para que decidas qué escribir y con cuánta
profundidad. No se copian al documento.** Lo que se escribe es la forma duradera del hecho: *la
mayoría*, *buena parte*, *a bastante distancia*, *la excepción*, *rara vez*, *es el material más
frecuente del surtido*. Una proporción que **no** sea del catálogo sino del mundo —«el ópalo
lleva entre un tres y un diez por ciento de agua»— es mineralogía y se queda: la ingesta lee el
contexto, no el símbolo.

### Regla 6 — El contenido indexado empieza por los dos títulos

El fragmento que se indexa es `# Título del documento` + `## Título de la sección` + el texto.
Lo compone el código, no tú — pero condiciona **cómo titulas**. Los dos títulos entran a la vez
en el índice léxico y en el vector, y es lo único que desambigua fichas con el mismo esqueleto.

Consecuencia práctica: **los títulos de sección son concretos y llevan las palabras que alguien
buscaría**. `## Cuidados y limpieza en casa` cobra ese regalo; `## Cuidados` lo desperdicia. Y
cuando el encargo te da un título de sección literal, **lo copias tal cual**.

### Regla 7 — Cada documento aporta **una** pregunta de evaluación

En la marca `eval_question` del encabezado: la pregunta que un operador haría de verdad, en
lenguaje natural, y que **debe** recuperar una sección de ese documento. Ni genérica («¿qué es la
plata?») ni copiada del título. Una sola por documento.

---

## Qué devuelves

**Solo los ficheros Markdown de este encargo**, uno por documento, cada uno precedido por una
línea con su ruta y nada más:

```
=== data/knowledge/<slug>.md ===
# Título
…
```

Sin comentario de introducción, sin resumen final, sin explicar lo que has hecho, sin preguntar.
Si algo del encargo te parece incompatible con las reglas, **escribe igualmente el documento
respetando las reglas** y no lo comentes.

---

## Documento de referencia

`data/knowledge/material-plata.md` está **escrito a mano** y es el patrón de todo el corpus. Estas
dos secciones son el tono, la longitud y el nivel de concreción que se esperan de ti:

```markdown
# Plata

<!-- doc_type: material -->
<!-- eval_question: ¿Por qué se pone negra la plata y cómo se limpia en casa? -->

## Qué es y cómo se reconoce

<!-- claim_scope: general -->

La plata que se usa en joyería casi nunca es plata pura, porque la pura es demasiado blanda para
sostener un cierre o un engaste. Lo habitual es la plata de ley: una aleación de 925 milésimas de
plata y 75 de otros metales, casi siempre cobre, que aporta la dureza. De ahí viene el número
`925` que aparece punzonado en el interior de un aro, en la placa de un cierre o en el reverso de
un colgante.

Su color es un blanco frío, algo más gris que el del oro blanco y bastante más luminoso que el
del acero. Al tacto pesa más de lo que su tamaño sugiere. Una pieza de plata recién pulida
refleja como un espejo; una que lleva tiempo en uso pierde ese brillo de fábrica y gana un tono
más suave, que no es suciedad sino uso.

## Qué lo estropea

<!-- claim_scope: general -->

El enemigo principal es el azufre del aire y de la propia piel: no oxida la plata, la sulfura, y
el resultado es esa capa oscura que aparece antes en las zonas que menos se rozan. Va rápido en
ambientes húmedos y cerca del mar.

El cloro de la piscina es distinto y peor, porque ataca la aleación y no solo la superficie: deja
un aspecto mate que ya no vuelve con un paño. El agua salada acelera el oscurecimiento y, si
queda sal seca en un cierre, lo agarrota.

También cuentan la cosmética y la química doméstica. Cremas, aceites solares, perfumes, lacas,
tintes, lejía y productos de limpieza dejan residuo o atacan directamente. Y el roce constante
contra otra pieza en el mismo bolsillo raya la superficie pulida, que es el acabado más delicado
de todos.
```

Fíjate en lo que **no** hay: ni una orden, ni un precio, ni una pieza concreta, ni una frase que
dependa de otra sección.

---

## Evidencia medida que justifica este bloque

Etiquetas de talla en los 1.200 productos del catálogo:

| Etiqueta | Productos | Etiqueta | Productos |
|---|---:|---|---:|
| `S` | 122 | `mini` | 21 |
| `pequeño` | 108 *(inflado por prosa)* | `grande` | 15 |
| `M` | 103 | `XS` | 10 |
| `L` | 87 | `mediano` | 6 |
| `XL` | 83 | `extramini` | 1 |
| | | **`XXS` y `XXL`** | **0** |

Cruce `tipo de pieza × etiqueta`, las doce combinaciones más frecuentes:

```
  pendientes  pequeño  34      colgante    M        26      pulsera     S        22
  pendientes  S        30      pendientes  M        25      anillo      M        21
  colgante    S        27      anillo      XL       25      pulsera     pequeño  21
  anillo      S        26      anillo      L        23      pendientes  XL       20
```

**El hallazgo que funda este bloque entero: la letra no es una talla de dedo, es el tamaño de la
pieza.** Se aplica a pendientes, colgantes, collares, pulseras y anillos por igual, y el tipo que
**más** la usa —`pendientes`, el 24,4 % del surtido— no tiene talla en el sentido de ajuste. El
documento de medidas deja de ser «inventar una tabla de milímetros» y pasa a **describir una
convención que los datos demuestran**.

Dato derivado, que se cita en la ficha de regalo: `pendientes` 24,4 % + `colgante` 16,0 % +
`cadena` 4,2 % = **44,6 % del surtido no depende de talla de ajuste**.

**`XXS` y `XXL` están en el vocabulario y en cero productos.** No se fingen inexistentes: la
convención los explica y los marca **por encargo**.

---

## La convención de la casa: literal, y sin margen para reinterpretarla

Esto no lo decides tú. Está fijado y **se transcribe exactamente como está aquí**.

`XS`–`XL` **no es ningún sistema normalizado de talla de anillo**. No es la española (número), ni
la ISO 8653 (circunferencia en milímetros), ni la estadounidense (número), ni la británica de
letras `A`–`Z` —donde `L`, `M` y `N` sí son tallas pero `XS` y `XL` no existen—. Es una **escala
de prenda** aplicada a todo el catálogo, y para una red de puntos de venta en hoteles y en el
aeropuerto de Menorca es la elección correcta: quien compra allí no vuelve a por un ajuste, no
sabe su talla española y a menudo compra para regalar.

La convención tiene **tres capas**:

1. **La letra mide la pieza, en todo el catálogo.** Una capa, no dos: la joyería no mantiene dos
   sistemas de etiquetado.
2. **El anillo es la única pieza donde la letra además compromete un ajuste**, y por eso la única
   con tabla de equivalencia. Esa tabla vive en **un solo documento**, `tallas-anillos`.
3. **La aritmética es estándar y la asignación es de la casa.** `circunferencia (mm) = talla
   española + 40` es la regla española de toda la vida y el diámetro se deriva de la
   circunferencia: comprobable fuera, luego **`general`**. Que `M` sean las tallas 13-15 y no las
   12-14 es una decisión del establecimiento, luego **`establecimiento`**.

**La tabla, que se copia carácter a carácter en la sección que se indica más abajo:**

```
| Letra | Talla española | Circunferencia interior | Diámetro interior | Disponibilidad |
|---|---|---|---|---|
| XXS | 4 – 6 | 44 – 46 mm | 14,0 – 14,6 mm | Por encargo |
| XS | 7 – 9 | 47 – 49 mm | 15,0 – 15,6 mm | De surtido |
| S | 10 – 12 | 50 – 52 mm | 15,9 – 16,6 mm | De surtido |
| M | 13 – 15 | 53 – 55 mm | 16,9 – 17,5 mm | De surtido |
| L | 16 – 18 | 56 – 58 mm | 17,8 – 18,5 mm | De surtido |
| XL | 19 – 21 | 59 – 61 mm | 18,8 – 19,4 mm | De surtido |
| XXL | 22 – 24 | 62 – 64 mm | 19,7 – 20,4 mm | Por encargo |
```

Tres tallas españolas enteras por letra, tramos contiguos y sin solape, `XXS` y `XXL` **por
encargo y no de surtido**. Hay un test que comprueba la aritmética de esa tabla fila a fila: si
cambias un número, falla.

**Las cuatro reglas de oficio** que modulan la elección, todas `general`:

- Una **banda ancha** —más de 6 mm— calza más prieta: se sube una talla española.
- **Nudillo marcado**: se elige por el nudillo y se sube una talla; con bolas de ajuste el aro no
  gira después.
- Se mide **al final del día y a temperatura normal**, nunca tras el baño en agua fría. **En
  verano el dedo varía hasta una talla entera**, que es precisamente el caso de esta red de
  puntos de venta.
- **Entre dos tallas, se sube.** En verano, siempre.

**Qué aro se puede ajustar y cuál no**, y esto tiene que decir **exactamente lo mismo** aquí, en
las fichas de material y en la política de reparaciones —hay un test que compara los tres—:

- **Ajustable hasta ±2 tallas**: aro liso, o con labrado parcial, en **plata** o en **oro**.
- **No se ajusta de talla**: una alianza con piedras en todo el contorno; un aro cuyo motivo
  recorre la banda entera, porque el dibujo se rompería; un aro hueco; **cualquier pieza con baño
  de oro**, porque el ajuste quema el baño y obliga a rebañarla; y el **latón** y el **acero**,
  que en la práctica no se ajustan.

Los términos `mini`, `extramini`, `pequeño`, `mediano` y `grande` describen **el motivo de la
pieza** y **nunca** un ajuste de anillo. No los uses jamás como equivalencia de talla de dedo:
hay un test que lo comprueba.

---

## Los documentos de este encargo

Son **cuatro ficheros**, todos con `doc_type: talla`.

### `data/knowledge/tallas-como-se-miden-en-nuestro-catalogo.md` — título `# Cómo se miden las piezas de nuestro catálogo`

Cinco secciones, títulos literales, en este orden, y con **estos** `claim_scope`:

| Sección | `claim_scope` | Extra |
|---|---|---|
| `## La letra es el tamaño de la pieza, no la talla de dedo` | `general` | lleva `source_ref: medicion-catalogo-2026-09-06` |
| `## A qué tipos de pieza se aplica la letra` | `general` | lleva `source_ref: medicion-catalogo-2026-09-06` |
| `## mini, pequeño, mediano y grande: escalas de motivo` | `general` | lleva `source_ref: medicion-catalogo-2026-09-06` |
| `## Qué mide la letra en cada tipo de pieza` | **`establecimiento`** | |
| `## Qué piezas no llevan talla` | `general` | lleva `source_ref: medicion-catalogo-2026-09-06` |

Las secciones con `source_ref` llevan la marca `<!-- source_ref: medicion-catalogo-2026-09-06 -->`
junto a la de `claim_scope`, porque su afirmación se re-mide contra el catálogo con un comando.

**Este documento no repite la tabla de anillos.** La nombra y remite a `tallas-anillos`. Dos
versiones de la misma tabla en dos documentos es una incoherencia esperando a que alguien
corrija una sola de las dos. Y las cifras del cruce medido **no se copian**: te dicen dónde se
concentra el uso de la escala para que lo describas en palabras —los peldaños centrales, los
tipos de pieza que más recurren a la letra—, nunca para que el documento las enuncie (regla 5).

### `data/knowledge/tallas-anillos.md` — título `# Tallas de anillo`

**Siete** secciones, títulos literales, en este orden, y con **estos** `claim_scope`:

| Sección | `claim_scope` |
|---|---|
| `## Cómo medir tu talla en casa con hilo o papel` | `general` |
| `## Medir a partir de un anillo que ya tienes` | `general` |
| `## Cuándo medir: temperatura, hora del día y nudillo` | `general` |
| `## De la talla española a los milímetros` | `general` |
| `## Nuestra escala de letras: qué talla es cada una` | **`establecimiento`** |
| `## Entre dos tallas, y por qué la banda ancha cambia la respuesta` | `general` |
| `## Qué aro se puede ajustar y cuál no` | `general` |

- `## De la talla española a los milímetros` enuncia **`circunferencia = talla española + 40`** y
  que el diámetro sale de dividir la circunferencia entre π. Aritmética, sin tabla.
- `## Nuestra escala de letras: qué talla es cada una` es **la única sección de todo el corpus que
  lleva la tabla**, copiada carácter a carácter de arriba, con la columna `Disponibilidad`. Deja
  la tabla y como mucho dos frases cortas: la sección no puede pasar de 1.200 caracteres.
- `## Cuándo medir…` y `## Entre dos tallas…` recogen las cuatro reglas de oficio.
- `## Qué aro se puede ajustar y cuál no` recoge la lista de arriba y contiene, literalmente, las
  palabras **baño de oro**, **latón** y **acero** entre lo que **no se ajusta de talla**, y
  **plata** y **oro** entre lo ajustable **hasta ±2 tallas**.

### `data/knowledge/tallas-collares-y-cadenas.md` — título `# Medidas de collares y cadenas`

Cuatro secciones, todas `general`, títulos literales y en este orden:

`## Longitudes habituales y dónde cae cada una` · `## Cómo medir la longitud que ya usas` ·
`## Escote y longitud` · `## Colgante y cadena: cuándo no pegan`

Longitudes en centímetros y dónde cae cada una en el cuerpo —gargantilla, base del cuello, sobre
el escote, bajo el escote, largo—, y que el rango cambia con la anchura del cuello. Cómo medir
con un hilo o con una cadena que ya se usa. Qué longitud pide cada escote. Y el desajuste
frecuente: un colgante pesado en una cadena fina, un colgante grande en una cadena corta que lo
deja bajo la barbilla, y el grosor mínimo de eslabón que un colgante pide para no deformarlo.

### `data/knowledge/tallas-pulseras-y-tobilleras.md` — título `# Medidas de pulseras y tobilleras`

Cuatro secciones, todas `general`, títulos literales y en este orden:

`## Cómo medir muñeca y tobillo` · `## Cuánta holgura dejar` ·
`## Rígidas y abiertas: se miden distinto` · `## Tobilleras: la medida que casi nadie sabe`

Medir con un hilo o una tira de papel por encima del hueso; la holgura habitual y cómo cambia
según se quiera ajustada o suelta; que una pulsera rígida no se mide por el contorno sino por el
diámetro interior y por el paso del hueso de la mano, y que una abierta se mide por la apertura;
y la tobillera, que pide bastante más holgura de la que la gente supone y cuya medida casi nadie
conoce de memoria.
