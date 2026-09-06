# knowledge/v1 — Encargo 6: piel, seguridad y regalo

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

**Piel y seguridad.** Los materiales del catálogo, ordenados por lo que importa aquí:

| Material | Productos | Riesgo real para una piel sensible |
|---|---:|---|
| `plata` | 630 | Muy bajo. El sospechoso es el níquel de una soldadura, no la plata |
| `oro` | 418 | Muy bajo en amarillo; el blanco puede llevar níquel en la aleación |
| `latón` | 77 | **El más alto del surtido**: cobre que verdea y posibles trazas de níquel |
| `baño de oro` | 36 | Bajo mientras el baño está entero; **el riesgo aparece cuando se va** y asoma el metal base |
| `acero` | 3 | Bajo, pero *inoxidable* no significa *sin níquel* |

Dos de esas filas son el documento entero: **el níquel casi nunca está donde el cliente cree que
está**, y el riesgo de una pieza bañada **no es constante en el tiempo**, sino que empieza el día
en que el baño se retira.

**Regalo.** Del cruce medido de tipo de pieza y etiqueta de talla sale el dato que sostiene el
documento de regalo: `pendientes` 24,4 % + `colgante` 16,0 % + `cadena` 4,2 % = **44,6 % del
surtido no depende de talla de ajuste**. Casi la mitad del catálogo se puede regalar sin saber
una medida — y el otro documento del bloque explica las tradiciones que hacen que la gente
regale joyas en primer lugar.

Recuerda que la letra `XS`–`XL` **mide la pieza y no el dedo** en todo el catálogo, y que el
anillo es el único tipo donde además compromete un ajuste. La tabla de equivalencia vive en
`tallas-anillos` y **no se repite aquí**: se remite a ella.

---

## Los documentos de este encargo

Son **cuatro ficheros**, todos con `doc_type: faq`. Todas las secciones son
`claim_scope: general` **salvo una**, marcada abajo.

### `data/knowledge/niquel-y-piel-sensible.md` — título `# Níquel y piel sensible`

Cinco secciones, todas `general`, títulos literales y en este orden:

`## Qué es la dermatitis de contacto` · `## Dónde suele estar el níquel en una joya` ·
`## Qué materiales del catálogo son seguros` · `## Latón y baño de oro: el riesgo real` ·
`## Piercings recientes y lóbulos irritados`

Qué es una alergia de contacto y en qué se diferencia de una irritación por humedad y jabón
atrapados bajo la pieza —el enrojecimiento que sigue exactamente el contorno del aro y cede al
secar—. Dónde vive el níquel de verdad: soldaduras, vástagos de pendiente, muelles de cierre,
alma de una pieza chapada y aleaciones de oro blanco. La tabla de arriba, en prosa. Y el
apartado de piercings recientes, que es el caso más delicado del mostrador: una perforación
abierta es una herida, y ahí el criterio no es de joyería sino sanitario, así que la sección
describe el riesgo y remite a un profesional sanitario en lugar de dar una pauta.

Este documento **no promete** que ninguna pieza sea libre de níquel: describe dónde está el
riesgo. Prometer sería un compromiso de la casa y esta sección no es del bloque de servicio.

### `data/knowledge/joyas-y-ninos.md` — título `# Joyas y niños`

Cuatro secciones, todas `general`, títulos literales y en este orden:

`## Pendientes de bebé: cierre y peso` · `## Piezas pequeñas y riesgo de atragantamiento` ·
`## Cuándo perforar y qué material elegir` · `## Cadenas y seguridad al dormir`

El cierre de rosca frente al de presión y por qué el peso importa en un lóbulo pequeño; el riesgo
de atragantamiento con piezas menudas y con lo que se puede desprender de una joya —una bola de
ajuste, una perla suelta, un cierre pequeño—; qué material es el más tolerado para una
perforación reciente y por qué la decisión de cuándo perforar es sanitaria y familiar y no de
joyería; y por qué una cadena al cuello durante el sueño es el caso en el que un cierre que cede
es una ventaja y no un defecto.

Tono especialmente cuidado en este documento: **descriptivo, informativo y sin alarmismo**, y sin
una sola frase que diga a nadie qué hacer con su hijo.

### `data/knowledge/ocasiones-y-tradicion.md` — título `# Ocasiones y tradición`

Cuatro secciones, todas `general`, títulos literales y en este orden:

`## Aniversarios y sus materiales` · `## Bodas y alianzas` · `## Comunión y bautizo` ·
`## Cumpleaños y piedras del mes`

Es el documento donde la **regla 4 se pone a prueba**, porque el tema invita al imperativo
comercial y hay que resistirlo. Se escribe «el aniversario de plata es el 25.º y el de oro el
50.º, y el de perla el 30.º», nunca «regálale plata por su 25.º». Aniversarios y sus materiales
tradicionales; la costumbre de la alianza y de dónde viene el dedo en que se lleva, que además
varía por país; las piezas asociadas a comunión y bautizo en la tradición española; y la lista de
piedras del mes, que es una convención comercial del siglo XX y conviene decirlo así, sin
presentarla como si fuera antigua.

### `data/knowledge/regalar-sin-saber-la-talla.md` — título `# Regalar sin saber la talla`

Cinco secciones, títulos literales, en este orden, y con **estos** `claim_scope`:

| Sección | `claim_scope` | Extra |
|---|---|---|
| `## Qué tipos de pieza no dependen de talla` | `general` | lleva `source_ref: medicion-catalogo-2026-09-06` |
| `## Cadenas y colgantes: la apuesta segura` | `general` | |
| `## Pendientes: por qué casi siempre valen` | `general` | |
| `## Si es un anillo: cómo averiguar la talla sin preguntar` | `general` | |
| `## Nuestra política de cambio por talla` | **`establecimiento`** | |

La primera sección se apoya en la medición del surtido —sin dar el porcentaje, regla 5— y lleva su marca
`<!-- source_ref: medicion-catalogo-2026-09-06 -->` junto a la de `claim_scope`. La cuarta recoge
los trucos de oficio —tomar prestado un aro que la persona ya usa y medir su diámetro interior,
fijarse en la mano en que lo lleva, y que el dedo cambia con la estación— y remite a
`tallas-anillos` para la equivalencia, **sin repetir la tabla**. La quinta es un compromiso de la
casa: describe que existe un cambio por talla, sin plazos ni condiciones, que viven en el
documento de devoluciones.
