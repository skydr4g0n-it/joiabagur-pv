# Corpus de conocimiento comercial — guía de autoría

Este directorio es **el segundo índice del sistema**. `ai.product_document` responde a
«enséñame anillos de plata»; esto responde a «¿este anillo se puede mojar?», que no vive en
ningún producto sino en el conocimiento general de la joyería.

Cada fichero `*.md` de este directorio es **un documento**, cada sección `##` es **un chunk**, y
cada chunk es **una cita**: `<slug-del-documento>#<slug-de-la-sección>`. Con el corpus en git,
esa cita no solo resuelve — **abre el fichero y el encabezado** y deja comprobar la afirmación.

`README.md` y cualquier fichero que empiece por `_` **no** son documentos: el cargador los
ignora. Todo lo demás bajo `data/knowledge/*.md` entra al índice.

---

## Formato de un documento

```markdown
# Plata

<!-- doc_type: material -->
<!-- eval_question: ¿Por qué se pone negra la plata y cómo se limpia en casa? -->

## Qué es y cómo se reconoce

<!-- claim_scope: general -->

La plata de ley que se usa en joyería es una aleación de 925 milésimas de plata pura…

## Nuestra garantía sobre el baño

<!-- claim_scope: establecimiento -->
<!-- source_ref: politica-garantia -->

La casa responde del baño durante…
```

- **El nombre del fichero es el slug del documento.** `material-plata.md` → `material-plata`.
  No se renombra a la ligera: renombrar un fichero rompe todas las citas que apuntaban a él.
- **`doc_type` es obligatorio** y sale de un vocabulario cerrado que el esquema ya restringe:
  `material`, `talla`, `politica`, `faq`. El quinto valor, `guion_venta`, **está prohibido en
  este corpus** — ver la regla 4.
- **`eval_question` es obligatoria**: es la pregunta con la que la mini-medición comprueba que
  el documento se recupera (regla 7).
- `source_ref` es **opcional**, a nivel de documento y a nivel de sección.

---

## Las siete reglas de autoría

Ninguna de las siete se confía al autor: **la ingesta las valida y falla nombrando el fichero y
la sección**. Un corpus que se valida solo con buena voluntad es un corpus que deriva.

### 1. Un `# Título`, y después solo secciones `##`. Nada de texto antes de la primera

Entre el título del documento y el primer `##` solo caben líneas en blanco y marcas
`<!-- clave: valor -->`. Cualquier otra cosa **falla la ingesta**.

No es formalismo: un preámbulo sin sección produciría un fragmento **sin encabezado propio**, o
sea sin localizador — una cita que resuelve y no localiza, que es exactamente lo que este corpus
existe para evitar. Tampoco se usan encabezados `###` o más profundos: la unidad de cita es la
sección de segundo nivel y solo esa.

### 2. Una sección = una afirmación citable, 80-250 palabras, **tope duro de 1.200 caracteres**

Por encima del tope, la ingesta **falla**. El código **no trocea por su cuenta**: parte el autor,
que es quien sabe dónde acaba una afirmación. Un troceado automático produciría fragmentos sin
encabezado propio, o sea sin localizador otra vez.

> **El que manda de los dos límites es el de caracteres.** 1.200 caracteres son unas 190
> palabras de español, así que el tramo alto del rango de palabras no cabe. En la práctica se
> escribe apuntando a **110-170 palabras**, y el rango 80-250 queda como lo que es: la horquilla
> de intención, no el límite que se comprueba.

Misma disciplina que el tope de 1.000 caracteres que C06b aplica al copy sintético.

### 3. `claim_scope` obligatorio por sección, en comentario HTML bajo el encabezado

Dos valores, y son **dos comportamientos**, no dos etiquetas:

| Valor | Qué significa | Qué se puede hacer con él |
|---|---|---|
| `general` | Comprobable **fuera** de la joyería: química, alérgenos, medidas, geografía | Se puede leer a un cliente |
| `establecimiento` | **Compromiso de la casa.** Hoy ilustrativo | Se marca en la cita y **nunca se afirma sin confirmar** |

Se declara **por sección y no por documento**, porque un mismo documento lleva de los dos tipos:
en `tallas-anillos`, «circunferencia = talla + 40» es aritmética española comprobable fuera, y
«una `M` es la 13-15» es una decisión de esta casa. Mismo fichero, dos estatus.

Sin la marca, la ingesta **falla**. El chunker la **retira antes de componer el contenido**, de
modo que no entra ni en el embedding ni en el `tsvector`.

### 4. Modo descriptivo, **nunca imperativo**

«El aniversario de plata es el 25º», no «ofrécele plata por su 25º».

No es una preferencia de estilo. Un fragmento **imperativo** recuperado dentro de un prompt es
indistinguible de una instrucción: convertiría el propio corpus en **superficie de inyección**.
Por eso este corpus tiene **cero documentos `guion_venta`**, y por eso el tono comercial vive en
`ai-service/prompts/`, versionado, y no aquí.

> El corpus guarda **hechos para citar**; el prompt guarda **instrucciones para obedecer**.

### 5. Ninguna sección nombra un SKU, un producto, un precio **ni una cifra del catálogo**

Una sola regla con dos mitades, porque son la misma idea: **el conocimiento es general y tiene
que seguir siendo cierto cuando el catálogo cambie.**

**Ni artículo ni precio.** Si una afirmación solo vale para una pieza, no es conocimiento, es
catálogo, y el catálogo ya tiene su índice. Un precio, además, contradice la regla de los
placeholders `{{price}}` / `{{stock}}`. Prohibido y comprobado en la ingesta: referencias tipo
`SKU01` o `ref. 4432`, y precios en cualquier forma (`48 €`, `48 EUR`, `48 euros`).

**Ni recuentos del surtido.** Es la mitad que más engaña, porque una cifra medida parece rigor y
es lo contrario. «`pequeño` encabeza con 71 etiquetas» deja de ser cierto en cuanto entra o sale
un producto, y un documento que caduca **en silencio** es peor que uno que nunca dio el número:
la cita sigue resolviendo, sigue localizando, y ahora sostiene una falsedad con sello de
verificada. Que aparezca un producto más de oro, o que desaparezcan todos los de zafiro, no
puede invalidar un documento del corpus.

Prohibido y comprobado en la ingesta: recuentos de productos, piezas, fichas o colecciones
(`144 piezas`, `1.168 productos`, `veintiocho colecciones`) y proporciones del surtido
(`el 24,4 % del catálogo`, `un doce por ciento de las piezas`).

Lo que **sí** se escribe es la forma duradera del hecho: *la mayoría*, *buena parte*, *a
bastante distancia*, *la excepción*, *rara vez*, *es el material más frecuente del surtido*. Y
una proporción que **no** es del catálogo sino del mundo —«el ópalo lleva entre un tres y un
diez por ciento de agua»— es mineralogía y se queda: la ingesta lee el contexto, no el símbolo.

La evidencia medida no desaparece, cambia de sitio: decide **qué documentos existen y con
cuánta profundidad**, y vive en los prompts de bloque de `ai-service/prompts/knowledge/v1/` y en
el informe de la medición. Nunca en el texto citable.

### 6. El contenido indexado empieza por los dos títulos

```
# <título del documento>
## <título de la sección>

<texto>
```

Lo compone el chunker, no el autor — pero condiciona cómo se titula. El `tsvector` es **columna
generada sobre `content`**, así que los dos títulos entran a la vez en el índice léxico y en el
embedding. Es lo único que desambigua nueve fichas de material con el mismo esqueleto, el mismo
registro y el mismo vocabulario, y sale gratis. Un título de sección genérico (`## Cuidados`)
desperdicia ese regalo; uno concreto (`## Cuidados y limpieza en casa`) lo cobra.

### 7. Cada documento aporta **una pregunta** a la evaluación

En la marca `eval_question` del encabezado. Es la pregunta que un operador haría y que **debe**
recuperar una sección de ese documento. Junto a ellas viven, en `_eval/out-of-domain.yaml`, las
preguntas **fuera de dominio** cuyo resultado correcto es **ninguna cita**.

---

## Lo que este corpus es, y lo que no

**Es sintético.** Lo redactó un asistente con revisión humana bloque a bloque; los textos
comerciales que el diseño daba como «a pedir al negocio» nunca llegaron. El sidecar
`_corpus.meta.json` sella modelo, versión de prompt e instante.

**Y la verificación de citas es estructural, no semántica.** Confirma que la fuente citada
existía y se recuperó, **no que diga la verdad**. Un corpus inventado puede pasar la comprobación
al 100 % citando algo falso *con sello de verificado*, que es peor que no citar.

Por eso `claim_scope` no es decoración: es el único mecanismo que separa lo que se puede afirmar
de lo que solo esta joyería puede confirmar. La composición exacta —cuántas secciones de cada
tipo— la publica el sidecar y la declara `ai-service/README.md`.

---

## Comprobar antes de commitear

```bash
cd ai-service
uv run --system-certs python -m jbg_ai.knowledge validate   # las siete reglas, sin base de datos
uv run --system-certs python -m jbg_ai.knowledge stats      # recuento por doc_type y claim_scope
```

Indexar es otro comando y necesita base de datos y clave de embeddings:

```bash
uv run --system-certs python -m jbg_ai.indexing sync-knowledge
```
