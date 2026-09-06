# knowledge/v1 — Encargo 3: piedras

> **3 documentos · 16 secciones.** Uno de los ocho encargos en que se produce el corpus de
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

Apariciones de cada piedra del vocabulario cerrado en los 1.200 productos:

| Piedra | Prod. | Piedra | Prod. | Piedra | Prod. |
|---|---:|---|---:|---|---:|
| `coral` | **102** | `esmeralda` | 22 | `ópalo` | 7 |
| `ámbar` | **75** | `diamante` | 16 | `jade` | 6 |
| `ónix` | 57 | `lapislázuli` | 14 | `madreperla` | 6 |
| `piedra` *(genérico)* | 33 | `rubí` | 13 | `turquesa` | 6 |
| `perla` | 30 | `amatista` | 11 | `nácar` | 5 |
| `cuarzo` | 26 | `citrino` | 10 | `circonita` | 3 |
| `topacio` | 23 | `granate` | 9 | `ágata` · `hematites` | 2 · 2 |
| `zafiro` | 23 | `obsidiana` | 8 | `labradorita` | 1 |

**Sin una sola aparición, 8 de 33:** `malaquita`, `howlita`, `aventurina`, `ojo de tigre`,
`piedra luna`, `amazonita`, `jaspe`, `calcedonia`. **No reciben sección propia**: el corpus
describe el surtido que existe, no el vocabulario que podría existir. Puedes nombrar alguna de
pasada dentro de una lista si el sentido lo pide, pero ninguna lleva sección.

**El hallazgo que decide la organización de este bloque:** las dos piedras más frecuentes —`coral`
102 y `ámbar` 75, 177 productos entre las dos— **son materia orgánica**, que es la categoría de
cuidado más frágil y la que peor tolera el consejo genérico. Por eso los tres documentos se
agrupan **por régimen de cuidado y no por dureza ni por familia mineralógica**: lo que decide
cómo se limpia una piedra es si es orgánica, si es porosa, si está tratada y si aguanta
ultrasonidos — no su posición en la escala de Mohs.

`perla` y `nácar` aparecen aquí como materia orgánica, pero **la ficha de la perla ya existe**
como ficha de material (`material-perla`). Este bloque la trata en su contexto orgánico sin
repetir lo que aquella dice.

---

## Los documentos de este encargo

Son **tres ficheros**, todos con `doc_type: material` y **todas sus secciones
`claim_scope: general`**. Ni una sola sección `establecimiento` en este encargo: la mineralogía y
el cuidado de una gema son comprobables fuera de esta joyería.

### `data/knowledge/piedras-materia-organica.md` — título `# Piedras de materia orgánica`

**Siete** secciones, títulos literales y en este orden:

`## Qué tienen en común y por qué son distintas` · `## Coral` · `## Coral y especies protegidas` ·
`## Ámbar` · `## Perla y nácar` · `## Limpieza: lo único que se puede hacer` ·
`## Qué las arruina en una tarde`

Lo que comparten: **no son minerales**, vienen de un ser vivo, son blandas, porosas y sensibles
al ácido y al calor. Coral: esqueleto calcáreo de colonia marina, el color y el pulido, la
diferencia con el coral teñido o reconstituido. La sección de especies protegidas es una sección
propia y no una nota: el coral rojo mediterráneo está regulado, hay especies con comercio
restringido por CITES y otras que no, y el material de joyería antiguo o de acopio anterior a la
regulación no es lo mismo que el de extracción actual — descríbelo con precisión y sin
tremendismo. Ámbar: resina fósil, ligerísima, cálida al tacto, se electriza al frotar, se raya
con una uña dura, se disuelve con acetona y alcohol; cómo se distingue del plástico y del copal.
Perla y nácar: capas de aragonito, la misma fragilidad. La limpieza es paño húmedo y secado, y
nada más. En la última sección, lo que las arruina de verdad en una tarde: ultrasonidos, vapor,
lejía, acetona, limpiadores de plata, agua de piscina y sol directo mantenido.

### `data/knowledge/piedras-cuarzos-y-gemas-facetadas.md` — título `# Cuarzos y gemas facetadas`

**Cinco** secciones, títulos literales y en este orden:

`## Qué son y por qué aguantan bien` · `## Ónix, cuarzo, amatista y citrino` ·
`## Ágata y granate` · `## Zafiro, rubí y diamante` · `## Circonita: qué es y qué no`

El régimen de cuidado fácil del bloque: minerales duros, no porosos, que toleran agua tibia y
jabón neutro y el cepillado suave. Ónix y la familia del cuarzo —cuarzo, amatista, citrino—: qué
son, sus colores, que la amatista y el citrino destiñen con luz solar prolongada y con calor.
Ágata y granate, con sus bandas y su color. Corindones —zafiro y rubí— y diamante: los más duros,
los que menos cuidado piden, y aun así la advertencia que sorprende: **duro no es lo mismo que
tenaz**, y un diamante se astilla por un golpe seco en el canto. Circonita: **no es un diamante y
no es una imitación fraudulenta**, es óxido de circonio sintético, un material de pleno derecho
con su propio brillo; se raya antes que el diamante y se apaga con el uso, y eso es lo honesto
que hay que saber de ella.

### `data/knowledge/piedras-opacas-porosas-y-tratadas.md` — título `# Piedras opacas, porosas y tratadas`

**Cuatro** secciones, títulos literales y en este orden:

`## Por qué porosa cambia todo el cuidado` · `## Esmeralda: la gema tratada que parece dura` ·
`## Lapislázuli, turquesa, jade, ópalo y obsidiana` · `## Nunca ultrasonidos, nunca vapor`

La idea que estructura el documento: **la porosidad manda sobre la dureza**. Una piedra porosa
absorbe agua, jabón, aceite, crema y perfume, y lo absorbido cambia su color de forma
irreversible. La esmeralda es el ejemplo perfecto y merece su sección: es dura, parece robusta, y
está casi siempre tratada con aceite o resina para cerrar las fisuras — el ultrasonido y el vapor
retiran ese tratamiento y dejan visible lo que ocultaba. Lapislázuli y turquesa, porosas y
teñibles; jade y sus imitaciones; el ópalo, que además lleva agua en su estructura y se cuartea
si se reseca; la obsidiana, vidrio volcánico con canto cortante. Y la sección final, que es la
regla que se lleva de todo el bloque, enunciada en modo descriptivo y no como orden.
