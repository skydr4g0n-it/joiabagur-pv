# knowledge/v1 — Encargo 5: uso, cuidado y entorno

> **4 documentos · 18 secciones.** Uno de los ocho encargos en que se produce el corpus de
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

La red de puntos de venta de esta joyería son **hoteles y el aeropuerto de Menorca**. No es un
dato de color: es lo que hace de este bloque el más útil del corpus, porque la joya que se compra
allí se estrena esa misma semana, en la playa, en la piscina y con crema solar encima.

Del catálogo, lo que condiciona lo que hay que decir:

| Material | Productos | % | Qué le hace el agua |
|---|---:|---:|---|
| `plata` | 630 | 52,5 % | La tolera; el cloro y la sal, no |
| `oro` | 418 | 34,8 % | La tolera bien |
| `latón` | 77 | 6,4 % | Verdea |
| `hilo` | 63 | 5,2 % | Encoge, destiñe, pierde la cera |
| `baño de oro` | 36 | 3,0 % | **El cloro se lo lleva** |

Y las piedras más frecuentes del surtido —`coral` 102, `ámbar` 75, `perla` 30— son **materia
orgánica**, la categoría que peor tolera el agua de piscina, el sol mantenido y el sudor.

Es decir: el material mayoritario aguanta razonablemente, pero **los dos casos frágiles —el baño
y la materia orgánica— son exactamente los que un cliente de hotel se lleva a la piscina**. Ese
contraste es el contenido del documento de playa y piscina, y la razón de que sea el más largo
del bloque.

---

## Los documentos de este encargo

Son **cuatro ficheros**, todos con `doc_type: faq`. Todas las secciones son
`claim_scope: general` **salvo una**, marcada abajo.

### `data/knowledge/cuidados-generales.md` — título `# Cuidados generales de una joya`

Cuatro secciones, títulos literales, en este orden, y con **estos** `claim_scope`:

| Sección | `claim_scope` |
|---|---|
| `## La regla de la última en ponerse y la primera en quitarse` | `general` |
| `## Limpieza semanal: paño, agua tibia y jabón neutro` | `general` |
| `## Lo que nunca: lejía, dentífrico, ultrasonidos` | `general` |
| `## Cuándo llevarla a la joyería` | **`establecimiento`** |

La primera sección enuncia el principio que ordena todo el bloque: la joya se pone la última,
después del perfume, la crema y el peinado, y se quita la primera, antes de la ducha, el deporte
y la cama. Enunciado en modo descriptivo, no como orden.

La tercera desmonta los tres remedios caseros que más piezas arruinan: la lejía, que ataca la
plata y disuelve la soldadura; el dentífrico, que es un abrasivo y raya el pulido y se lleva el
baño; y el limpiador de ultrasonidos doméstico, que desmonta engastes, retira el tratamiento de
las gemas y arruina la materia orgánica.

`## Cuándo llevarla a la joyería` es `establecimiento`: describe en qué situaciones la casa
revisa una pieza —cierre que no cierra, engaste que suena, cadena que se ha estirado, pieza que
ha perdido el baño— sin prometer plazos ni condiciones, que viven en los documentos de servicio.

### `data/knowledge/joyas-playa-piscina-y-deporte.md` — título `# Joyas en la playa, la piscina y el deporte`

**Seis** secciones, todas `general`, títulos literales y en este orden:

`## Agua salada: qué le hace a cada material` · `## Cloro: el enemigo del baño y de la plata` ·
`## Arena y roce` · `## Crema solar y aceites` · `## Agua fría y anillos que se caen` ·
`## Qué joya sí puede ir a la playa`

Es el documento diferencial de este corpus. Material por material en la primera sección: las
cifras de arriba te dicen a cuáles dedicar más espacio y **no se copian al texto** (regla 5). El cloro merece sección propia
porque es el único agente que **ataca la aleación y no solo la superficie**, y porque es lo que
retira un baño de oro en una temporada. La arena es abrasivo puro y raya el pulido y el baño. La
crema solar deja película, se acumula bajo los engastes y amarillea el hilo. `## Agua fría y
anillos que se caen` es la sección que evita una pérdida real: el dedo encoge con el agua fría
—hasta una talla entera— y el aro se va sin que nadie lo note. La última recoge la respuesta
práctica: qué combinaciones aguantan bien el día de playa y cuáles no.

### `data/knowledge/perfume-cremas-y-cosmetica.md` — título `# Perfume, cremas y cosmética`

Cuatro secciones, todas `general`, títulos literales y en este orden:

`## El orden correcto: joya al final` · `## Perfume y plata` ·
`## Cremas, aceites y el baño de oro` · `## Laca, tintes y productos de peluquería`

El alcohol y los aceites esenciales del perfume sobre la plata y sobre las piedras porosas; la
película grasa de las cremas, que atrapa suciedad y apaga el brillo, y lo que le hace al baño; y
la peluquería, que es el escenario que más piezas estropea de golpe —laca sobre unos pendientes,
tinte y agua oxigenada sobre una cadena, decolorante sobre un aro—.

### `data/knowledge/guardar-y-viajar-con-joyas.md` — título `# Guardar y viajar con joyas`

Cuatro secciones, todas `general`, títulos literales y en este orden:

`## Cada pieza en su bolsa` · `## Humedad, luz y calor` · `## Cadenas que se enredan` ·
`## Viajar: qué va en cabina y qué no`

La separación como principio: cada pieza aparte para que no se rayen entre ellas, con la
bolsita antioxidante para la plata. Los tres enemigos del sitio donde se guarda —el baño es
húmedo, la ventana da luz directa y calor, el coche al sol arruina una resina—. El truco real
contra el enredo de cadenas: cerrar el cierre y estirarlas en plano, y el nudo que ya se ha hecho
se abre con una gota de aceite y dos alfileres, con paciencia. Y el viaje: lo de valor va en
cabina, cada pieza en su bolsa, y el estuche rígido para lo que tiene engaste.
