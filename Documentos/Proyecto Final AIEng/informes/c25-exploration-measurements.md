# C25 — mediciones de la exploración: la fusión no fusiona, y el juez es ciego a lo que el change añade

**Sesión del 2026-09-11**, sobre la rama `c25-recalibrate-ranking-and-abstention` nacida de `ai-eng`
con C24 ya archivado. Todas las cifras salen de artefactos versionados en el repositorio
—`ai-service/evals/`, los informes de C18a, C21 y C22— o de ejecutar el código vivo
(`jbg_ai.retrieval.fusion`, `jbg_ai.retrieval.synonyms`, `jbg_ai.retrieval.lexical`) sobre el
golden set. **No se ha levantado la base de datos**: lo que exige base queda marcado como
medición pendiente de la fase 0 del change, no afirmado.

---

## 0. Resumen: seis hallazgos, y dos refutan la ficha

| # | Hallazgo | Consecuencia |
|---|---|---|
| 1 | **El golden set es estructuralmente ciego a las señales de C25.** `criterion.md` no menciona stock ni rotación | Un barrido que maximice nDCG@5 converge a **peso 0** en todas las señales. Hace falta métrica objetivo distinta del guardarraíl |
| 2 | **El golden set corre sin POS**, así que `qty_bucket` llega `NULL` y la penalización de C22 **no se disparó ni una vez** en el run publicado | Hay que introducir el POS separando la **señal** (`LEFT JOIN`) del **alcance** (`INNER JOIN`) |
| 3 | **El criterio de aceptación del §11.2 es inalcanzable con señales de negocio.** Recall@5 real 0,483 contra 0,85 | Criterio relativo, y la brecha absoluta se declara |
| 4 | **La fusión vigente no fusiona: concatena.** Con `wC = 0,33`, los 60 documentos léxicos ganan al #1 vectorial **siempre**, y el modelo predice la posición 33 que se midió | Es un **defecto aritmético**, no un peso mal calibrado. Fusión en dos etapas con pesos por rama |
| 4b | La rama léxica tiene además **el doble de huecos**: hasta 120 documentos distintos frente a los 60 de la vectorial | La etapa 1 corrige huecos y voto con un solo cambio |
| 5 | **La partición de ajuste está saturada y adversarialmente compuesta**: 6 de 8 en el techo, y 7 de 8 salen de la lista curada de C20/C21 | La lectura que decide pasa a ser `new`; `tuning` es diagnóstico de contaminación |
| 6 | **`coordination` se calcula, viaja y se tira.** Cuarto cable pelado del subsistema | Habilita la regla adaptativa a coste cero |

**Refutan la ficha de C25:** la penalización de variante ambigua (§6) y la calibración de
`1-2` frente a `3+` (§5). Las dos se cierran por medición, no por argumento.

---

## 1. El juez es ciego a lo que el change añade

[`criterion.md`](../../../ai-service/evals/golden/criterion.md) fija la escala:

```
 2  Se lo enseño al cliente como respuesta a ESA consulta.
 1  Mismo piece_type o familia, pero falla UN atributo que la consulta nombró.
    O bien: sustituto plausible que el operador ofrecería como segunda opción.
 0  Todo lo demás.
```

Se leyó el documento entero buscando *stock*, *disponibilidad* o *rotación*. **No aparecen.**
La relevancia se juzga contra lo que la pieza **es**, nunca contra lo que la tienda **tiene**.

De ahí la aritmética que gobierna el change: si A es grado 2 y está agotado y B es grado 0 y
hay cuatro, ordenar `B, A` **baja** el nDCG@5. La reordenación por disponibilidad es ortogonal
a la etiqueta y, en el margen, hostil a ella.

No es un defecto del golden set. C24 hizo bien en no meter disponibilidad en la rúbrica: la
habría mezclado con cobertura de surtido, que es la separación que C22 defendió al dejar el
conjunto sin escopar. El defecto es de la **ficha de C25**, que pide *«pesos calibrados contra
el golden set»* — una vara que no mide su eje.

### La salida: métrica derivada, sin re-etiquetar

```
g_efectivo(doc) =  grado                si qty_bucket ≠ '0'
                   máx(grado − 1, 0)     si qty_bucket = '0'
```

**No introduce una constante nueva: reutiliza la semántica de la propia escala.** El grado 1 ya
está definido como *«sustituto plausible que el operador ofrecería como segunda opción»*, y una
pieza que no se puede poner sobre el paño es exactamente eso. Bajar un peldaño por agotamiento
es aplicar la rúbrica, no torcerla.

Precedente metodológico dentro del proyecto: C24 ya publica **dos lecturas** de la misma
anotación (`nDCG@5` y `nDCG@5 bin`) y declara la comparación robusta porque ordenan igual. Ésta
es la tercera lectura, declarada antes de medir, con la etiqueta intacta.

**Alternativas descartadas.** (a) nDCG@5 como objetivo tal cual: el barrido demostraría w=0 y
«calibrar» sería teatro. (b) Re-etiquetar con disponibilidad en la rúbrica: mueve
`criterion.md`, mueve `golden_set_version` y destruye la comparabilidad con la línea base
publicada. (c) Inventar un multiplicador (`+0,3 si hay stock`): el número mágico que el apunte
de S10 avisa de no inventar.

---

## 2. Hoy la señal no existe en la evaluación

[`v2-hibrido.yaml`](../../../ai-service/evals/configs/retired/v2-hibrido.yaml) *(retirada por C25bis: histórica y no ejecutable)* corre con
`pos_prefilter: false`, y su propio comentario declara la consecuencia. En
[`search.py`](../../../ai-service/src/jbg_ai/retrieval/search.py) eso significa literalmente
`NULL AS qty_bucket`, y `_out_of_stock` devuelve `False` para `None` **por diseño explícito**
(*«`None` no es cero»*).

> **En las 192 filas del run `d9222333` la penalización de disponibilidad no se disparó ni una
> vez.** La funcionalidad que C22 entregó está sin medir, y C25 no puede calibrar lo que no
> corre.

### La separación que el código todavía no tiene

```
   HOY — un solo flag hace dos cosas
   scoped=True  →  INNER JOIN scope  +  s.qty_bucket     restringe Y lee
   scoped=False →  sin join,  NULL AS qty_bucket         ni restringe ni lee

   C25 — dos conceptos, dos parámetros
   scope_pos_id   →  INNER JOIN   (restringe el universo)   el prefiltro de C22
   signal_pos_id  →  LEFT  JOIN   (sólo lee la señal)       la señal de C25
```

Con `scope_pos_id = None` y `signal_pos_id = <POS de referencia>` se mide la reordenación por
disponibilidad **sin pagar el coste de recall del prefiltro**, que es justo la confusión que la
config de C22 declara como no medida. El CTE ya existe y ya selecciona `qty_bucket`: sólo hay
que desacoplar el `JOIN` del `LEFT JOIN` y partir el relleno de los dos huecos de `_scoped()`.

### Qué POS de referencia

Reparto de ceros medido por C22: **MAO-AIR 34,4 %** (143 de 416), **FORNELLS 12,0 %**,
**HT-GALDANA 11,7 %**. Calibrar donde la señal apenas aparece es calibrar sobre ruido; calibrar
sólo en el extremo es ajustar a una tienda atípica.

**Decisión: calibrar en MAO-AIR (rica en señal) y validar en FORNELLS y HT-GALDANA.** Es la
disciplina de las tres lecturas de C24 trasplantada al eje POS. Once POS × rejilla sería
inviable; tres es asequible y contesta la objeción.

`HT-ARTRUTX` queda excluido: surtido cero, responde 503 (heredado de C24).

---

## 3. El criterio de aceptación es inalcanzable tal como está escrito

El `qa.md` de C24 lo dejó por escrito: *«`Recall@5` sobre la porción real es 0,483 contra 0,85.
No es un fallo de este change —que entrega el juez, no las mejoras que el juez apruebe— pero es
el dato que C25 tiene que mover.»*

```
  Recall@5 real   0,483  ──────────────────────────▶  0,85    (+0,37)

  cuánto mueve una palanca DE RELEVANCIA, medido:
     barrido de wC (0,33 → 1,0)   →  nDCG@5 +0,057 global, y la regla lo vetó
  cuánto mueve una palanca ORTOGONAL:
     señales de negocio            →  ≤ 0 sobre relevancia pura, por construcción
```

El recall a 5 depende de **qué** entra en la ventana; las señales sólo reordenan lo que ya
entró. **Decisión: criterio relativo** —`v2b` bate a `v2` y `v3` bate a `v2b` en las tres
lecturas por encima del margen— y la brecha absoluta se declara como limitación del README.

Precedente: C18 ya encontró que *«el umbral del §7.5 no existe, y el plan se contradecía»*. El
0,85 y el 0,75 se fijaron antes de que existiera un golden set y antes de saber que
`relevant_total` puede valer 144 para una consulta.

---

## 4. La fusión vigente no fusiona: concatena

### 4.1 De dónde salen los pesos vigentes

Del informe de C21, que **se recusa a sí mismo**: *«The rubric is the lexical branch's own
objective function. A hit is a top-ten result with the piece type and a material the query
named... so a lexical arm scores well here by construction. These figures fix a starting point,
not a verdict.»* Nadie eligió 0,33 contra 1,00; salió de contar aciertos con una vara que la
rama léxica no puede fallar.

### 4.2 La aritmética

`score(d) = Σᵢ wᵢ / (k + rangoᵢ(d))`, con `k = 60`, profundidad `60`,
`w_typed = w_expanded = 0,50`, `w_vector = 0,33`. La rama léxica suma **1,00** votos.

| régimen | voto del documento léxico | `wC` mínimo para que el #1 vectorial entre en el top-5 | para ser #1 |
|---|---|---:|---:|
| Sólo la lista **expandida** devuelve (el AND de `websearch` no casa) | 0,50/(60+r) | **0,469** | 0,500 |
| **Ambas** listas léxicas devuelven el mismo documento | 1,00/(60+r) | **0,938** | 1,000 |

**`wC` vigente = 0,33, por debajo de los cuatro umbrales.** Y el caso extremo lo dice todo: un
documento léxico en el **rango 60** —el peor puesto posible— puntúa 0,008333; el mejor documento
que sólo vio la rama vectorial puntúa 0,33/61 = **0,005410**. Los 60 documentos léxicos ganan al
#1 vectorial, en toda consulta, siempre.

El óptimo que el barrido de C24 encontró (0,75-1,0) es **exactamente el intervalo que cubre los
dos umbrales de cruce**. El barrido no descubrió un peso mejor: descubrió la aritmética.

### 4.3 La prueba empírica

Dónde cae, en el híbrido, el documento de grado 2 que la rama vectorial pone en el #1
(categoría `descripcion-sin-anclaje`, run `d9222333`):

| consulta | pos. en `v1-vectorial` | pos. en `v2-hibrido` |
|---|---:|---:|
| `joya con forma de concha marina` | 1 | 3 |
| `la raiz retorcida de un arbol viejo` | 1 | 1 |
| `la campanita que se cuelga a los bebes para proteger` | 1 | **33** |
| `follaje seco que cae en septiembre` | 1 | **33** |
| `una bicicleta antigua` | 1 | **33** |
| `un molusco que se agarra a las piedras` | 9 | **53** |

Posición 33 en tres consultas distintas no es casualidad:

```
q06, q08, q10 — los 32 primeros del híbrido son SÓLO léxicos     : true
                la cola conserva EXACTAMENTE el orden vectorial   : true
```

**Los 32 documentos léxicos primero, y detrás la lista vectorial intacta.** No hay fusión: hay
una partición dura. El premio al consenso que justifica RRF sólo opera dentro del bloque léxico.

Y el modelo lo reproduce: ejecutando `fuse()` con `wC = 0,33` y una lista léxica de 32
documentos, el #1 vectorial cae en la **posición 33**. El diagnóstico queda cerrado
cuantitativamente.

### 4.4 El daño, consulta a consulta

De las 12 de `descripcion-sin-anclaje`: el híbrido **mejora en 1, empata en 7 y empeora en 4**.
Tres de esas cuatro pasan de 1,000 a 0,000 o 0,100. Seis fallan en las dos ramas (son
genuinamente difíciles), así que el techo de la categoría está limitado por el corpus.

Delta `v2 − v1` por categoría, para ver que el daño es local y no general:

| categoría | n | `v1` | `v2` | delta |
|---|---:|---:|---:|---:|
| `descripcion-sin-anclaje` | 12 | 0,431 | 0,172 | **−0,259** |
| `piedra` | 4 | 0,785 | 0,747 | −0,038 |
| `fuera-de-dominio` | 5 | 0,000 | 0,000 | 0,000 |
| `variante-talla` | 7 | 0,817 | 0,830 | +0,014 |
| `subjetiva` | 5 | 0,502 | 0,665 | +0,163 |
| `sinonimos` | 6 | 0,729 | 0,984 | +0,254 |
| `materiales` | 5 | 0,682 | 0,968 | +0,287 |
| `lexico-exacto` | 4 | 0,500 | 1,000 | +0,500 |

La fusión **aporta mucho donde hay anclaje léxico y destruye donde no lo hay**. Eso es lo que
hace que subir `wC` globalmente sea un compromiso y no una corrección.

### 4.5 El segundo sesgo, que nadie había visto: los huecos

`typed` aporta hasta 60 documentos y `expanded` otros 60, **cada uno truncado a `depth` por
separado**. La rama léxica puede meter hasta **120 documentos distintos** en la fusión, frente a
los 60 de la vectorial. La configuración actual sobrepondera el lado léxico por dos vías
independientes: **el doble de huecos y el triple de voto**.

---

## 5. La corrección: fusión en dos etapas con pesos por rama

```
   ETAPA 1 — dentro de la rama léxica
     typed     (websearch AND del texto tal cual)   w_int = 0,5
     expanded  (OR de los grupos de C20)            w_int = 0,5
          └─── fuse() ───▶ UNA lista léxica ordenada   (sólo sobrevive el ORDEN)

   ETAPA 2 — entre ramas
     léxica    (la lista de la etapa 1)             w_lex
     vectorial (<=> coseno)                         w_vec
          └─── fuse() ───▶ lista final
```

Las dos listas léxicas se juntan con el mismo RRF y por el mismo motivo que arriba: `ts_rank`
de un AND de `websearch` y `ts_rank` de un OR de `plainto` con tallas de coordinación distintas
son **escalas incomparables**, que es el pantano que RRF existe para evitar.
[`fusion.py`](../../../ai-service/src/jbg_ai/retrieval/fusion.py) ya es puro y sin dominio a
propósito, y su docstring anuncia que C25 lo importaría.

### Lo que compra

1. **El voto total de la rama pasa a ser exactamente `w_lex`**, sin depender de cuántas de sus
   listas dispararon. Muere la ambigüedad de dos regímenes (0,469 frente a 0,938), que es una
   propiedad de la consulta que nadie declaró y que hoy gobierna el resultado.
2. **Arregla el reparto de huecos**: la rama léxica entra con 60, los mismos que la vectorial.
3. **Regalo:** en la etapa 2 hay exactamente dos listas, que son exactamente dos ramas, así que
   `len(ranks) > 1` **es** el consenso entre ramas. Desaparece el matiz que hoy
   `_fuse_branches` tiene que explicar por escrito y `low_confidence` deja de necesitar
   excepción.

### Lo que cuesta, declarado

De la etapa 1 **sólo sobrevive el orden**: la magnitud del consenso intra-léxico se aplana. Un
documento que era #1 en las dos listas y otro que era #1 en una y #40 en la otra pueden acabar
adyacentes. La defensa es que eso es lo que RRF hace en todos sus niveles —su premisa es que el
rango es la moneda comparable— y que el **orden** del premio al consenso se conserva íntegro.

El reparto interno **0,5 / 0,5 se fija y no se barre**: la evidencia de C21 establece que las
dos listas son *necesarias* —el `typed` rescata los nueve productos llamados «Sortija», el
`expanded` rescata `gargantilla`— no que una valga más. Una asimetría sería un número mágico
sin hipótesis, y una perilla sin hipótesis se ajusta al ruido de 48 consultas.

### Medido: sólo importa el cociente, y la banda útil es estrecha

Ejecutando `fuse()` real, los órdenes con `0,5/0,5`, `1,0/1,0` y `0,2/0,2` son **idénticos**:
escalar los dos pesos escala todos los scores y preserva el orden. **El barrido es de una
dimensión.**

Con `ρ = 1` el resultado se explica en una frase: los documentos que las dos ramas señalan
primero, y detrás un **round-robin perfecto** — léxico 1, vectorial 1, léxico 2, vectorial 2…

Posición final del #1 vectorial según `ρ = w_vec / w_lex`, con lista léxica de 60 sin consenso
(predicción del modelo y medición con `fuse()`, coincidentes en los once puntos):

| `ρ` | posición | ¿top-5? |
|---:|---:|:---:|
| 0,33 *(equivalente a hoy)* | 61 | no |
| 0,50 | 61 | no |
| 0,75 | 22 | no |
| 0,85 | 12 | no |
| 0,90 | 8 | no |
| **0,95** | **5** | **sí** |
| 0,98 | 3 | sí |
| 1,00 | 2 | sí |
| ≥ 1,10 | 1 | sí |

**La banda útil es `ρ ∈ [0,9 ; 1,1]`, y la rejilla de C24 (0,33 · 0,5 · 0,75 · 1,0 · 1,5 · 2,0)
tenía un solo punto dentro.** Por eso su óptimo parecía un filo de cuchillo: la rejilla no podía
ver la banda.

**Rejilla recomendada:** `ρ ∈ {0,6 · 0,8 · 0,9 · 0,95 · 1,0 · 1,05 · 1,1 · 1,25}`, normalizada
como `w_lex + w_vec = 1`. **Punto de partida `ρ = 1,0` (0,5 / 0,5)**, con su frase de
justificación: *«cada rama tiene un voto; el mejor resultado de cada rama ocupa uno de los dos
primeros puestos, y lo que las dos señalan va primero»*. Es un valor **de principio**, no
ajustado.

**Alternativa descartada: subir `wC` a 1,0 sin más.** Es el óptimo del barrido, pero 1,000 es
exactamente el umbral de cruce del régimen 2 —un peso elegido sobre una discontinuidad no es una
calibración, es una coincidencia— y paga globalmente (`sinonimos` −0,039, `materiales` −0,010)
un daño que es local. Se conserva como red de seguridad si la adaptativa no se sostiene.

---

## 6. La regla adaptativa, y el denominador que casi sale mal

La señal ya existe y se tira: `coordination` viaja en
[`LexicalHit`](../../../ai-service/src/jbg_ai/retrieval/ports.py) y **el orquestador no la lee
nunca**. Cuarto cable pelado del subsistema, tras `tsv`, la expansión y `qty_bucket`. C21 confió
en una ponderación adaptativa *emergente* —*«a query with no counting group at all leaves the
ordering to `ts_rank`, and through it to the vector branch»*— y **no emerge**: `ts_rank` sigue
ordenando 60 documentos que siguen ganando todos.

```
                coordinación del MEJOR documento de la lista expandida
   cobertura = ───────────────────────────────────────────────────────
                grupos contables cuya tsquery NO es vacía

   w_lex_efectivo = w_lex × cobertura
```

El numerador es **gratis**: la lista viene `ORDER BY coordination DESC`, así que
`expanded_hits[0].coordination` *es* el máximo.

### El denominador es la trampa

Ejecutando `expand_query` + `counting_flags` sobre el golden set, las palabras vacías **cuentan
como grupo**:

```
'sortija de plata'       →  ['sortija','anillo','aro de dedo']  ['de']  ['plata']
'una bicicleta antigua'  →  ['una']  ['bicicleta']  ['antigua']
'anillo de plata y oro'  →  ['anillo','aro de dedo'] ['de'] ['plata'] ['y'] ['oro']
```

`plainto_tsquery('spanish','de')` es una **tsquery vacía**: no casa con nada, nunca. Con el
denominador ingenuo —todos los grupos contables— el efecto es el contrario del deseado:

| consulta | ingenuo | corregido | nDCG@5 actual |
|---|---:|---:|---:|
| `sortija de plata` | 2/3 = **0,67** ✗ | 2/2 = **1,00** ✓ | 1,000 |
| `bano de oro` | 1/1 = 1,00 | 1/1 = 1,00 ✓ | 1,000 |
| `gargantilla dorada` | 1/1 = 1,00 | 1/1 = 1,00 ✓ | 0,903 |
| `anillo de plata y oro` | 3/5 = **0,60** ✗ | 3/3 = **1,00** ✓ | — |
| `una bicicleta antigua` | 1/3 = 0,33 | 1/2 = **0,50** ✓ | 0,000 |
| `follaje seco que cae en septiembre` | 1/6 = 0,17 | 1/4 = **0,25** ✓ | 0,100 |

**Con el denominador ingenuo la regla recortaría un tercio del peso léxico en `sortija de
plata`, que puntúa nDCG 1,000**: destruiría exactamente las categorías que existe para no tocar.

Grupos contables por categoría, medidos sobre las 48 juzgadas:

| categoría | n | contables mín | máx | media |
|---|---:|---:|---:|---:|
| `sinonimos` | 6 | 1 | 4 | 1,8 |
| `lexico-exacto` | 4 | 1 | 4 | 2,2 |
| `piedra` | 4 | 3 | 3 | 3,0 |
| `materiales` | 5 | 3 | 5 | 3,8 |
| `subjetiva` | 5 | 3 | 7 | 3,8 |
| `variante-talla` | 7 | 3 | 7 | 5,3 |
| `fuera-de-dominio` | 5 | 4 | 6 | 5,4 |
| `descripcion-sin-anclaje` | 12 | 3 | 11 | **7,8** |

### Propiedades

- **Cero parámetros.** Es la propiedad que más vale: el aviso de S10 es sobre números mágicos y
  `w_lex × cobertura` no tiene ninguno.
- **Efecto predicho cero** sobre `materiales`, `sinonimos`, `lexico-exacto` y `piedra`, cuya
  cobertura es 1,00. **Predicción falsable**: si alguna se mueve, o el denominador está mal o la
  implementación está mal. Test: `test_full_coverage_leaves_the_lexical_weight_untouched`.
- **Implementación sin viaje extra:** el denominador es constante por consulta y se calcula en la
  **misma sentencia** que ya tally-a la coordinación, con `numnode(<fragmento>) > 0`.
- **Alternativa de reserva:** forma binaria —«¿cubrió *todos* los grupos expresables? si no,
  `α`»— con **un** parámetro declarado, que entra como segunda fila candidata del barrido en
  lugar de sustituir a la primera.

---

## 7. La partición de ajuste está saturada y adversarialmente compuesta

Las 8 consultas `in_tuning_set`, con sus cifras de `v2-hibrido`:

| qid | categoría | nDCG@5 | R@5 | P@3 | MRR | texto |
|---|---|---:|---:|---:|---:|---|
| q01 | `descripcion-sin-anclaje` | 0,631 | 1,000 | 1,000 | 1,000 | `joya con forma de concha marina` |
| q20 | `materiales` | **1,000** | 1,000 | 1,000 | 1,000 | `sortija de plata` |
| q21 | `materiales` | **1,000** | 1,000 | 1,000 | 1,000 | `aros de plata` |
| q22 | `materiales` | **1,000** | 1,000 | 1,000 | 1,000 | `pendiente de oro` |
| q34 | `sinonimos` | **1,000** | 1,000 | 1,000 | 1,000 | `bano de oro` |
| q35 | `sinonimos` | **1,000** | 1,000 | 1,000 | 1,000 | `anillo pequeno` |
| q36 | `sinonimos` | **1,000** | 1,000 | 1,000 | 1,000 | `dije de plata` |
| q38 | `sinonimos` | 0,903 | 1,000 | 1,000 | 1,000 | `gargantilla dorada` |

**Dos cosas, y la segunda es la grave.**

1. **6 de 8 están en el techo** del nDCG@5 y **las 8 en el techo** de Recall@5, P@3 y MRR. Una
   lectura saturada no puede mejorar: sólo empatar o caer.
2. **Las siete que no son q01 salen literalmente de la lista curada de C20/C21**, y en el informe
   de C21 todas marcan 10/10 en la rama léxica. La partición de ajuste **es el conjunto de
   consultas con el que se calibró la rama léxica**.

O sea: la condición *«mismo signo en las tres lecturas»* está vetando subir el peso vectorial
**con las consultas elegidas para que la rama léxica ganase**. Es el mismo error estructural que
C24 diagnosticó en la rúbrica de C21 —el juez emparentado con una de las partes— reproducido
dentro de su propia regla de decisión.

### La reformulación, y por qué no es ajuste *post hoc*

El arreglo **no** es eximir techos *ad hoc*. Es que C24 midió y publicó que el híbrido saca
**0,942 en ajuste contra 0,535 en nuevas**, y lo llamó *«la contaminación del conjunto de ajuste,
cuantificada»*. **Una partición contaminada es evidencia de sobreajuste del titular, no un grupo
de control.** Usarla como control es validar un modelo sobre su conjunto de entrenamiento y
rechazar todo cambio que baje el acierto en entrenamiento.

Ese argumento es visible **sin mirar el resultado del barrido**, que es lo que lo distingue de un
ajuste posterior.

> **Regla reformulada, a escribir y fechar antes de re-medir.** La lectura que decide es
> **`new`** (40 consultas, nunca vistas por ninguna calibración). `tuning` se reporta como
> **diagnóstico de contaminación** y no veta. Ninguna categoría medida cae más del margen. Y la
> partición de ajuste **crece** en la sesión de etiquetado, porque 8 consultas no arbitran nada
> en ninguna dirección.

Con esa regla, el hallazgo heredado de C24 —`wC = 1,0`, global +0,057, nuevas +0,073— pasa el
filtro. Con la regla actual **no pasa ninguna corrección de fusión, nunca**, sea cual sea su
mérito.

---

## 8. Abstención: la medición que falta no es la que C24 tomó

C24 midió y publicó la distribución **por documento**:

| grado | documentos | mínimo | mediana | máximo |
|---|---:|---:|---:|---:|
| 0 | 2.119 | 0,3268 | 0,5338 | 0,8710 |
| 1 | 852 | 0,2745 | 0,4668 | 0,7465 |
| 2 | 955 | 0,2071 | 0,5167 | 0,8008 |

Solape total, hueco **−0,4739**: ningún escalar separa un documento relevante de uno irrelevante.
**Cierto, y no es la cantidad que decide la abstención.**

```
  LO QUE DECIDE:  min(distancia) por CONSULTA
    de las 43 contestables   vs   de las 5 fuera de dominio
```

Se verificó: el JSONL por consulta del run `d9222333` guarda métricas y **no guarda distancias**
(`run_id, config_id, query_id, ndcg_at_5, …, abstained, relevant_total, ranked`). La cantidad no
existe en ningún artefacto.

Y hay precedente de que esa forma puede ser limpia: el corpus de conocimiento de C23 separó con
**exactamente** esa cantidad —0,5062 máximo de las contestables contra 0,5145 mínimo de las de
fuera, ocho milésimas de margen—. **Que las distribuciones por documento se solapen no implica
que las de mejor-acierto por consulta lo hagan**: son preguntas distintas, y la segunda gobierna
la abstención de la consulta entera.

**Decisión: medirla como primera tarea del change, antes de diseñar nada.** Si el hueco existe, la
abstención se resuelve con un escalar como en C23 y el alcance se abarata mucho. Si no, toca
regla relativa (`d ≤ d_min·(1+α)`) o cuantil por consulta, y hay una señal ya construida que
correlaciona con «estoy adivinando»: el `low_confidence` por ausencia de consenso entre ramas.

**Y esa medición gobierna la secuencia del change**, porque decide si el trabajo del umbral
**mueve la ventana** (escalar en el `WHERE` del SQL → fase A) o **no la mueve** (regla
post-recuperación → fase D).

### La categoría fuera-de-dominio tiene 5 consultas

Calibrar una regla de abstención con n=5 no es calibrar. Ampliarla es lo más barato que existe en
este golden set: por la propia rúbrica, en fuera-de-dominio **todo es grado 0**, así que no hay
etiquetado documento a documento — sólo hay que escribir consultas plausibles e imposibles.
**Pasar de 5 a 15-20** convierte la única cifra de aceptación alcanzable en una cifra creíble.

---

## 9. Dos puntos de la ficha refutados por medición

### 9.1 `1-2` frente a `3+`: se mantiene binario

`QtyBucket.From(quantity)` en .NET: `≤0 → "0"`, `1-2 → "1-2"`, `≥3 → "3+"`. Un bucket y nunca la
cantidad exacta, porque la proyección puede ir desfasada y guardar el número real invitaría a
mostrarlo; la cantidad la posee .NET.

La spec viva prohíbe hoy ordenar `1-2` contra `3+`, y C22 dejó escrito que la calibraría *«el
change de ranking que pueda hacerlo contra un golden set»*. **La pregunta se responde en contra
de calibrar, y por construcción:** con `g_efectivo`, los dos caen en la rama `qty_bucket ≠ '0'`,
ninguno pierde grado, y **no existe función objetivo que pueda ordenarlos**.

Se suma que la lectura de negocio tiene **signo ambiguo** —«quedan una o dos: que se venda» y
«quedan una o dos: puede que ya no estén» son las dos defendibles en un mostrador—, y cuando dos
lecturas legítimas se cancelan el peso honesto es cero. Se enseñan en todo caso; el desfase con
la caja es un problema de sincronización, no de ranking.

**Decisión: el binario se conserva, y se confirma con una medición** del reparto de `1-2` frente
a `3+` sobre los 6.050 pares asignados (pendiente de base). Un MUST heredado pasa a ser un MUST
respaldado.

### 9.2 Variante ambigua: es presentación, no ranking

Tres hechos verificados en el código:

**(a) El panel ya distingue las hermanas, pero no sabe que lo son.**
[`assisted-search-result-row.tsx`](../../../frontend/src/components/sales/assisted-search-result-row.tsx)
pinta `Talla {variantLabel}` en cada fila, así que cuatro tallas del mismo anillo **no** aparecen
como cuatro filas idénticas. Pero `familyId` no se usa en ninguna parte del panel del operador
—sólo en la pantalla de revisión de familias—, y `assisted.tsx` pinta la lista **en el orden
recibido**, con un comentario que declina reordenar.

**(b) La inundación está acotada por el tamaño real de las familias.** Reparto medido por C18a:
**44 familias de dos miembros, 55 de tres, 55 de cuatro, una de cinco y una de ocho**. De 156
familias, **sólo 2 podrían llenar cinco huecos**, y 99 no pueden llenar ni cuatro. Y el operador
ve **10** filas (`PAGE_SIZE = 10`), no 5.

**(c) La rúbrica ya resuelve bien el caso con talla nombrada, y penalizar rompe el caso sin
talla.** Con `anillo … talla L`, la hermana correcta es grado 2 y las demás grado 1, y nDCG
premia ese orden: `variante-talla` es la **mejor categoría** de `v2-hibrido` (0,830). Sin talla
nombrada, las cuatro hermanas son legítimamente grado 2 y diversificar **baja** el nDCG@5.

| | **Ranking** (penalizar) | **Presentación** (`groups[]`, §7.7) |
|---|---|---|
| Libera huecos | quitando tallas de la vista | metiendo las tallas en una tarjeta |
| Pierde el operador | deja de ver qué tallas hay | nada |
| Pierde la métrica | nDCG@5 baja con hermanas grado 2 | nada |
| Dueño | C25 | C30 / C36 |

La presentación **domina estrictamente**: un hueco de página, todas las tallas visibles, cero
coste de relevancia. Y penalizar convierte un problema de maquetación en **pérdida de
información**: si se hunden las hermanas, el operador no puede saber que existen —`family_id` no
se pinta— así que la segunda consulta no la hace porque no sabe que hace falta.

**Decisión: C25 no toca familias.** `test_ambiguous_variant_penalty_applies_only_within_family` se
refuta y se anota en el §0 del plan. Con una condición, para no refutarlo por argumento como ya
pasó una vez en este proyecto: **medir primero** cuántas consultas tienen 3+ hermanas en el
top-10, cruzando los `ranked` ya publicados con `product_document.family_id`. Si son muchas, la
respuesta **sigue siendo presentación**, pero `groups[]` sube de prioridad en C30/C36.

---

## 10. Lo que NO es riesgo

- **Latencia.** `p95` de recuperación **128,6 ms** contra 500 ms de presupuesto. C25 añade un
  `LEFT JOIN` sobre un CTE que ya se materializa y aritmética en Python sobre ≤60 candidatos.
  Ruido.
- **El índice HNSW.** Medido por C22: el planificador nunca lo usa a 1.168 filas y forzarlo cuesta
  13× y trunca a 40 de 60. C25 no lo toca.
- **Migración.** Ninguna: `ai.pos_projection` ya tiene `sales_30d`, `sales_90d`, `last_sale_at` y
  `computed_as_of` por fila.

---

## 11. El barrido sale casi gratis, y eso decide la forma del CLI

Las señales de negocio **no cambian qué candidatos se recuperan, sólo su orden**: `demote` es un
`sorted` estable que no elimina nada y devuelve la ventana completa. Por tanto:

```
  1× por consulta  →  recuperar (proveedor + SQL) y PERSISTIR la ventana de 60 con sus
                      señales: qty_bucket, sales_30d, family_id, score fusionado y ramas
  N× por rejilla   →  re-puntuar en memoria. Cero proveedor. Cero base. Exacto.
```

Frente al barrido de C24 —12 puntos × 48 consultas × proveedor—, el de las señales recorre
cientos de combinaciones en segundos. Y `test_calibration_sweep_is_reproducible` deja de ser una
promesa sobre semillas y pasa a ser **propiedad estructural**: la misma ventana persistida da el
mismo orden.

**Pero el orden de fases es obligatorio, no una preferencia**, porque el barrido barato depende de
que la ventana no cambie y la fusión la cambia:

```
  fase A — FIJAR LA FUSIÓN        barrido con proveedor · la ventana se mueve
              ↓ decisión congelada
  fase B — CAPTURAR las ventanas  1 vez por consulta, con sus señales
              ↓ ventana inmóvil
  fase C — FIJAR LAS SEÑALES      re-puntuado offline · cero proveedor
```

---

## 12. La tabla de seis filas: cada una aísla un cambio

| fila | qué aísla |
|---|---|
| `v0-nombre` · `v0-fts` · `v0-cag` · `v1-vectorial` | sin cambios; se re-corren sólo por procedencia |
| `v2-hibrido` | la fusión **plana** viva (`ρ ≈ 0,33`) — la línea base publicada |
| **`v2b-fusion`** | la fusión **por rama**, con adaptativa. **Sin** señales de negocio |
| **`v3-senales`** | `v2b` + disponibilidad + rotación |

**Sin `v2b`, un `v3` que mejorase sería inatribuible**: no se sabría si el mérito es de la fusión
o de las señales. Con ella, cada fila aísla un cambio.

**Consecuencia de implementación que no es negociable: la fusión plana se conserva como modo
seleccionable.** Si se sustituye, `v2-hibrido` deja de poder reproducir la línea base publicada y
la tabla pierde su fila de referencia.

### El *pool* se profundiza, así que se re-corre todo

`v2b` y `v3` promueven documentos que nadie juzgó. C24 construyó `unjudged@5` y el umbral
`NOT_COMPARABLE_UNJUDGED` para exactamente esto, y dejó los juicios apendables por
`(query_id, product_id)`. Pero al apendar **se mueve `golden_set_version`** y ninguna fila del
informe de C24 sigue siendo comparable: hay que **re-correr las seis**.

Las cuatro sin proveedor son gratis; `v1`/`v2` cuestan $0,0000002 por consulta. `v0-cag` es el
único incómodo —llama a un LLM y no es reproducible bit a bit— pero son 12 consultas a $0,002673,
o sea **tres céntimos**: se re-corre, para que la tabla entera comparta una sola procedencia.

Y el barrido **decide** sobre la versión vieja (legítimo: titular y candidatos se comparan contra
los mismos juicios, y `unjudged@5` marca la incomparabilidad) pero se **publica** sobre la nueva.
La disciplina de C24 obliga a **re-confirmar** el ganador contra el titular en la versión nueva:
un punto de rejilla, no la rejilla.

---

## 13. Rotación: no hay instrumento que la pueda aprobar

`sales_30d` está en el alcance de la ficha y **no existe métrica que pueda demostrar que ayuda**:

- **No hay gancho en la rúbrica.** El truco que justifica la transformación de disponibilidad
  —grado 2 agotado ≈ grado 1, «lo que enseñas después»— no tiene análogo: una pieza que rota no
  es *más relevante*.
- **La vía online no tiene volumen.** `ProductSearchEvents` tiene **31 filas y 12 textos**, todos
  escritos por el desarrollador.
- **La señal es rala:** **23,54 %** de los pares asignados tienen `sales_30d` no nulo (1.424 de
  6.050), contra el instante declarado `IndexFeed:SalesAsOf` y no contra el reloj de pared. C22
  dejó escrito: *«C25 calibra sobre 23,54 %, no sobre 16,28 %»*.

**Decisión: desempate declarado con peso fijo y argumentado, no calibrado**, y el README dice por
qué no puede calibrarse contra este golden set. La prueba de S10 se pasa: la frase que justifica
un desempate existe —*«entre dos piezas que el recuperador y el stock empatan, enseña la que se
vende»*— y la que justificaría un peso continuo, no.

**Nota sobre el apunte de S10**, que induce a equivocarse: su `temporal_weight` usa
`date.today()`. `last_sale_at` —4.021 filas no nulas, **más denso** que `sales_30d`— es tentador
como decaimiento exponencial, pero el mundo de C10 termina el **2026-08-23**, así que «hoy» tiene
que ser el `computed_as_of` de cada fila. Con reloj de pared el decaimiento se lleva la señal
entera a cero.

---

## 14. Zona: decimotercera vez que la ficha se queda corta

La ficha declara zona `retrieval/`. El change toca además `evals/` (configs, barrido, métrica
operativa, informe), `config/settings.py` (pesos por rama, `BUSINESS_DEFAULTS`, umbral) y
`evals/golden/` (ampliar fuera-de-dominio y la partición de ajuste). Va tras C08, C07, C15, C16,
C17, C18b, C20, C21, C22, C23 y C24.

Y el nombre deja de describirlo: `add-business-signals-ranking` cubriría un tercio.
**`recalibrate-ranking-and-abstention`**, con dos capacidades nuevas
—`business-signals-ranking` y `retrieval-abstention`— y deltas sobre `hybrid-fusion` y
`pos-projection`. **El número C25 se conserva**: renumerar rompería las referencias de C26
(`prereq C22, C25`) y C27 (`C10, C25`) a cambio de nada.

---

## 15. Mediciones pendientes de la fase 0 (exigen base levantada)

| # | Medición | Qué decide |
|---|---|---|
| **M1** | `min(distancia)` por consulta, contestables vs fuera-de-dominio | Si la abstención es un escalar (fase A) o una regla relativa (fase D) |
| **M2** | Cobertura por consulta y categoría, con el denominador corregido | Que la adaptativa dispare donde debe y **nunca** donde no |
| **M3** | Hermanas de familia en el top-10 por consulta | Refuta o resucita la penalización de variante |
| **M4** | Reparto de `1-2` frente a `3+` sobre los 6.050 pares asignados | Confirma el binario con una cifra |
