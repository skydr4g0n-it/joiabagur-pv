# knowledge/v1 — Encargo 8: glosario y Menorca

> **2 documentos · 13 secciones.** Uno de los ocho encargos en que se produce el corpus de
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

### El glosario

Es el **espejo semántico** del diccionario de sinónimos que el sistema ya usa para buscar, y el
documento que más ayuda a la rama léxica del índice: cuando alguien escribe «gargantilla», la
búsqueda tiene que llegar a algún sitio donde esa palabra esté explicada junto a sus vecinas.

Las equivalencias que el sistema ya conoce y que este documento hace explícitas: `sortija` y
`alianza` son anillos; `gargantilla` es un collar; `brazalete` y `esclava` son pulseras;
`criollas` y `aro` son pendientes; **`colgante` no es `collar`**, y esa confusión es la más
frecuente de todas. Un colgante es la pieza que cuelga; el collar es el conjunto.

### Menorca

De las 28 colecciones reales del catálogo, **doce llevan nombre de un lugar real de Menorca**:

| Colección | Productos | Colección | Productos |
|---|---:|---|---:|
| `Menorca` | 70 | `Cala Pregonda` | 20 |
| `Fiestas Menorca` | 15 | `Cala Presili` | 19 |
| `Es Caló Blanc` | 31 | `Binibeca` | 14 |
| `Biniacolla` | 26 | `Cavalleria` | 12 |
| `Sa Mesquida` | 23 | `Esencia Bagur` · `Joia Bagur` | 8 · 5 |

**Que las líneas lleven nombre de calas y cabos reales de Menorca es un hecho del catálogo, no
una historia inventada**, y la geografía de esos lugares es comprobable fuera de la joyería: por
eso casi todo este documento es `general`. Lo inventado sería atribuir a cada línea una intención
de diseño concreta, y eso es lo que va en la única sección `establecimiento`.

**La frontera que no se cruza.** El documento habla de **Menorca y de por qué las líneas se
llaman como se llaman**, nunca de los productos que contienen. Ninguna sección nombra un
artículo, y las once «colecciones» que no son líneas de diseño sino cajones operativos
—`Varios`, `Composturas`, `Tienda`, `Aros plata`, `Anillos`, `Pedida`, `Kit Huella`, `Cursos`,
`Maternidad`, `Melia`, `Papelería`, `Envío`— **quedan fuera y no se mencionan**. Es la frontera
que impide que el índice de conocimiento empiece a duplicar el de catálogo.

Geografía real que necesitas, y que se describe como lo que es:

- **Es Caló Blanc, Binibeca y Biniacolla** están en la **costa sur**: calas pequeñas, arena
  clara, roca caliza, agua turquesa y poco fondo. Binibeca es además el pueblo de casas
  encaladas y callejuelas estrechas.
- **Cala Pregonda, Cala Presili y Cavalleria** están en la **costa norte**: arena rojiza y
  oscura de origen ferruginoso en Pregonda, dunas y viento en Presili, y el **cabo de
  Cavalleria** con su faro, el punto más septentrional de la isla.
- **Sa Mesquida** está al noreste, con su torre de defensa, y es de las que más recibe la
  **tramontana**, el viento del norte que define el paisaje y la vegetación de esa costa.
- Las **fiestas de Sant Joan** son las de Ciutadella, en junio: el `jaleo`, los caballos
  menorquines negros que se alzan sobre las patas traseras entre la gente, y la `pomada`, la
  bebida de ginebra de la isla con limonada.
- La piedra de Menorca: el **marés**, arenisca dorada con la que está construida media isla, y la
  caliza del sur frente al material más oscuro y antiguo del norte. El color de la piedra explica
  el color de los pueblos.

---

## Los documentos de este encargo

Son **dos ficheros**, los dos con `doc_type: faq`.

### `data/knowledge/glosario-de-joyeria.md` — título `# Glosario de joyería`

**Seis** secciones, todas `claim_scope: general`, títulos literales y en este orden:

`## Collar, gargantilla, cadena y colgante: no son lo mismo` · `## Anillo, sortija y alianza` ·
`## Criollas, aros y pendientes de botón` · `## Pulsera, esclava y brazalete` ·
`## Cierres: mosquetón, reasa, presión` · `## Engastes y acabados`

Cada sección define su familia de términos y **dice explícitamente cuál es sinónimo de cuál y
cuál no**, que es lo que hace útil un glosario. La primera es la más importante y la que más se
consulta: colgante frente a collar. La de cierres describe cada tipo, para qué pieza sirve y cuál
falla antes. La de engastes cubre garra, bisel o chatón, grano y pavé, y los acabados —pulido
espejo, satinado, mate, envejecido u oxidado, martillado—, que son las palabras que aparecen en
las descripciones y que casi nadie sabe leer.

### `data/knowledge/menorca-y-el-origen-de-las-colecciones.md` — título `# Menorca y el origen de las colecciones`

**Siete** secciones, títulos literales, en este orden, y con **estos** `claim_scope`:

| Sección | `claim_scope` | Extra |
|---|---|---|
| `## Las colecciones llevan nombre de calas y cabos de Menorca` | `general` | lleva `source_ref: medicion-catalogo-2026-09-06` |
| `## Es Caló Blanc, Binibeca y Biniacolla: la costa sur` | `general` | |
| `## Cala Pregonda, Cala Presili y Cavalleria: la costa norte` | `general` | |
| `## Sa Mesquida y la tramontana` | `general` | |
| `## Las fiestas de Sant Joan y el jaleo` | `general` | |
| `## Marés, caliza y el color de la piedra menorquina` | `general` | |
| `## Qué inspira cada línea en nuestro taller` | **`establecimiento`** | |

La primera sección lleva su marca `<!-- source_ref: medicion-catalogo-2026-09-06 -->` junto a la
de `claim_scope`, y puede citar el recuento de líneas con topónimo como lo que es: un hecho
comprobable contra el propio catálogo.

Las cinco de geografía y cultura describen **los lugares**, no las piezas: quien lea esa sección
tiene que entender cómo es esa cala, no qué se vende con su nombre.

La última, `## Qué inspira cada línea en nuestro taller`, es la única `establecimiento` del
documento, y con razón: **la intención de diseño solo la puede confirmar la casa**. Descríbela
como intención declarada del taller, en términos de motivos y materiales —el color de la arena,
la forma de una ola, la roca, la luz—, **sin nombrar un solo producto**.
