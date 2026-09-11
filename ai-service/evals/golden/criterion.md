# Criterio de anotación del golden set — C24

**Escrito el 2026-09-07, antes de registrar ningún juicio.** Ése es su valor: un criterio
redactado después de ver los resultados describe lo que se etiquetó, no lo que se quería
etiquetar. La versión del conjunto (`golden_set_version`) queda registrada en cada ejecución,
de modo que una medición tomada hoy sigue siendo interpretable contra la vara que usó.

El conjunto lo etiqueta **una sola persona**. El diseño prometía doble etiquetado con
conciliación entre dos anotadores y el proyecto lo desarrolla una sola, así que esa mitigación
**no se ha aplicado**. Lo que la sustituye es este documento, la agrupación por categoría y la
relectura diferida de las dudosas — y la limitación se declara en el README en lugar de
disimularse. Los valores absolutos llevan el sesgo de un juicio único; **lo comparable entre
configuraciones sigue siendo válido, porque ese sesgo es el mismo en todas las filas**.

---

## La escala

```
 2  Se lo enseño al cliente como respuesta a ESA consulta.

 1  Mismo piece_type o misma familia, pero falla UN atributo que la consulta
    nombró explícitamente (talla, uno de varios materiales, color, piedra).
    O bien: sustituto plausible que el operador ofrecería como segunda opción.

 0  Todo lo demás.
```

**La frase que hace el trabajo es «un atributo que la consulta nombró explícitamente».**
Convierte el grado 1 en una comprobación de solape entre la consulta y la ficha —contable, no
impresionista— y es lo que mitiga la deriva del anotador a lo largo de una sesión. Si la
consulta no nombró el atributo, fallarlo no baja de 2; y si falla más de uno de los que sí
nombró, no sube de 0.

**Por qué tres grados y no dos.** El apunte de S10 recomienda binario por consistencia entre
anotaciones. Se descarta porque el binario destruye el caso crítico de este dominio: *anillo
correcto, talla equivocada* no es 0 ni es 2, y distinguirlo es justamente para lo que C18
construyó las familias y las variantes. La objeción del apunte no se ignora, se contesta con
datos: el informe publica **también** la lectura binaria derivada, `relevante ⇔ grado ≥ 1`, con
la misma regla para todas las configuraciones. Si las dos lecturas ordenan igual las
configuraciones, la robustez queda demostrada; si difieren, es un hallazgo y se publica como tal.

---

## Cómo se aplica, caso por caso

### Grado 2 — «se lo enseño al cliente»

La prueba es de mostrador, no de solape de palabras: con la ficha delante, ¿la pondría sobre el
paño ante un cliente que acaba de decir **esa** frase? Si sí, es 2, aunque la consulta y la ficha
no compartan ni una palabra. **Ese caso no es marginal: es el que este golden set existe para
medir**, porque la rúbrica que gobernó C20 y C21 no tiene diana para él.

- Una consulta descriptiva sin anclaje léxico se juzga contra lo que la pieza **es**, no contra
  lo que su texto **dice**. `una joya inspirada en el fondo del mar` es 2 para un colgante de
  erizo aunque su descripción no contenga ninguna de esas palabras.
- La consulta manda sobre el tipo de pieza sólo si lo nombra. `algo marinero de plata` no exige
  colgante: un pendiente de estrella de mar en plata es 2.
- Si la consulta nombra una piedra o un material, la pieza tiene que llevarlo de verdad.
  Parecerse no basta.

### Grado 1 — falla exactamente un atributo nombrado

Los tres casos que se van a repetir, y son los que dan sentido a la escala:

| Caso | Ejemplo |
|---|---|
| Talla equivocada | `anillo de estrella de mar talla L` → el mismo anillo en talla S |
| Uno de varios materiales | `anillo de plata y oro` → la misma pieza sólo en plata |
| Piedra o color equivocados | `anillo con amatista` → el mismo modelo con citrino |

Y la segunda mitad del grado: **sustituto plausible que el operador ofrecería como segunda
opción**. Misma familia, mismo motivo o misma colección, respondiendo a la misma intención con
otra pieza. `pendientes de erizo de mar` → el colgante de erizo de la misma colección es 1, no 2:
no es lo que se pidió, pero es lo que se enseña a continuación.

**Un atributo, no dos.** Talla equivocada **y** material equivocado es 0. La regla es contable
a propósito: en cuanto admite «bueno, casi», deja de ser reproducible al día siguiente.

### Grado 0 — todo lo demás

Incluye tres cosas que conviene nombrar porque tientan a puntuar alto:

- **Mismo tipo de pieza y nada más.** Un anillo cualquiera para `anillo con lapislázuli` es 0.
  El tipo de pieza cubre el 99 % del corpus: premiar por acertarlo es premiar por no hacer nada.
- **Coincidencia de palabra sin coincidencia de sentido.** Una pieza cuya descripción dice
  *«acaricia la piel»* no responde a `pulsera de piel`. Es el falso amigo que el diccionario de
  C20 ya excluye por escrito, y en el etiquetado se aplica igual.
- **Todo, en las consultas fuera de dominio.** Son plausibles dentro de la joyería y el catálogo
  no las puede satisfacer: su respuesta correcta es no tener ninguna respuesta. Si al etiquetar
  aparece un grado ≥ 1, la consulta estaba mal elegida y se sustituye — nunca se ablanda el
  juicio para salvarla.

---

## Reglas de proceso

**Se etiqueta por categoría, no por orden de identificador.** Las seis consultas de sinónimos
seguidas mantienen la vara más quieta que seis dispersas entre 48. Tres sesiones de ~1 h, que es
además la mitigación de la fatiga: siete horas seguidas activan el modo de fallo que ningún doble
etiquetado va a corregir aquí, porque no hay segundo anotador.

**Se etiqueta antes de mirar los resultados de C21.** El riesgo estructural de este conjunto es
nacer con el sesgo de la rúbrica que viene a arbitrar; si eso ocurre, confirmará a C21 por
construcción y el change no habrá arbitrado nada.

**Lo no juzgado cuenta 0, y se declara.** Es el supuesto estándar del *pooling*, y por eso el
informe publica `unjudged@5` por configuración: una fila con buena parte de su top-5 sin juzgar
es *visiblemente* no comparable en vez de silenciosamente injusta.

**Los juicios son apendables**, con clave `(query_id, product_id)`. Un change posterior profundiza
el *pool* sin re-etiquetar nada de lo ya hecho.

**Cada juicio guarda el `source_hash` del documento en el momento de etiquetarlo.** Si el texto
se reescribe después —`FIX1` reenriqueció 22 productos, y su plazo *«antes de que C24 etiquete»*
se cumplió por planificación—, el arnés informa cuántos juicios se apoyan en un texto que ya
cambió, junto a las métricas y no en un registro aparte.

**La duda se marca y se relee.** No se resuelve en caliente: se anota y se revisa en una pasada
posterior, que es lo que sustituye a la conciliación entre anotadores.
