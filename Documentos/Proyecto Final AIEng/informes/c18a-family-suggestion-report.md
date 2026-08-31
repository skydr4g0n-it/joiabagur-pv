# C18a — Informe del lote de familias asistidas

**Fecha de ejecución:** 2026-08-31 · **Change:** [`add-family-suggestion-and-approval`](../../../openspec/changes/add-family-suggestion-and-approval/) · **Rama:** `c18a-add-family-suggestion-and-approval`

Ejecutado por el camino real —`POST /api/ai/catalog/family-suggestions` en .NET, que llama a `POST /v1/families/suggest` en `jbg-ai` con el JWT interno— y no por un script suelto, porque el objeto de C18a es precisamente que ese camino exista y estampe lo que tiene que estampar.

---

## 1. Línea base, antes de tocar nada

| | |
|---|---|
| `Products` / `ProductAiProfiles` / `ai.product_document` | 1.200 / 1.200 / 1.200 |
| Documentos con `embedding` | 1.200 |
| **`ProductFamilies` / `ProductFamilyMembers`** | **0 / 0** |
| **Documentos con `family_id`** | **0** |
| Perfiles en `Approved` | 1.200 (ninguno rechazado nunca) |
| `embedding_version` | `openai/text-embedding-3-small:1536:source-text/v1` |

Respaldo previo en `pre-c18a.dump` (12 MB, esquemas `public` y `ai`), dentro del contenedor `jpv-pv-postgres`.

## 2. Resultado del lote

| | |
|---|---|
| Familias propuestas y creadas | **156** |
| Miembros | **486** |
| Tamaño de familia | mín. 2 · máx. 8 |
| Conflictos | **0** |
| `Origin = AiApproved` con aprobador e instante | **156 / 156** |
| Productos en dos familias | **0** |

Reparto de tamaños: 44 de dos miembros, 55 de tres, 55 de cuatro, una de cinco y una de ocho.

Por origen de dato: **87 familias sintéticas, 68 reales y 1 mixta**. La mixta es el hallazgo (d) de abajo.

## 3. Reconciliación del índice

**Una sola sincronización incremental**, nunca `--full`, reconciliando altas y bajas a la vez — el corpus se mueve una vez, y eso incluye las bajas:

```
POST /v1/index/sync  {"full": false}
  → upserted 486   deleted 32   skipped 0   failed 0
```

**486 y 32, ni uno más.** Es la verificación que exige el criterio de aceptación: el feed emitió exactamente los productos cuyo watermark se movió, y nada más. Los 486 son los miembros de familia; los 32, los tombstones de la sección 4.

Estado final del índice: **1.168 documentos** (1.200 − 32), **486 con `family_id`**, 467 con `variant_label` —los 19 restantes son piezas base, cuya etiqueta nula es un valor de variante legítimo y no una laguna—, **0 sin embedding** y **0 fallos** en `ai.sync_failure`.

Muestra de `doc_text` reindexado, con las dos líneas que hasta hoy estaban vacías en 1.200 de 1.200:

```
SKU: SKU686
Nombre: Pulsera Destellos de Zafiro M
Tipo: pulsera
Talla: M
Familia: Pulsera destellos de zafiro     ← nueva
Variante: M                              ← nueva
```

**Lo que NO cambió, verificado en vez de supuesto:** `embedding_version` sigue siendo un único valor, `openai/text-embedding-3-small:1536:source-text/v1`. Y ése es justamente el problema que obliga al orden: **el corpus de antes y el de después llevan la misma cadena**, así que nada distinguiría una medición tomada antes de una tomada después. Por eso C18a precede a C20, C21 y C24.

## 4. Entradas retiradas del índice: 32

Sacadas con `ProfileReviewStatus = Rejected`, **nunca con `IsActive = false`**: la tienda las vende —`Encargos` es una línea de caja de 10 €— y desactivarlas habría arreglado la búsqueda rompiendo el TPV. Verificado: **las 32 siguen con `IsActive = true`**.

| Categoría | n | Ejemplos |
|---|---|---|
| Servicios de taller | 8 | `Arreglos oro/plata`, `Cambiar hilo`, `Cambio elástico`, `Extensión plata`, `Comprobar pureza del oro y preparar el lingote` (75 €) |
| Experiencias | 5 | `Joyero por un día 2h/2:30h/3h`, `Taller semanal` |
| Señal de encargo | 2 | `Encargos Oro`, `Encargos plata` |
| Componentes (cierres) | 4 | `Presión Oro`, `Presión plata`, `Presión plata (x2)`, `Presión silicona (x2)` |
| Velas y regalo | 8 | `Vela`, `Vela Cerámica pequeña/grande`, `Pack Vela Navidad`, `Palo Santo`, `Caja experiens` |
| Merchandising «Neus» | 3 | `Postales`, `Iman`, `Llaberos` |
| Kit / envío | 2 | `Kit deja huella`, `Envio Nacional` |

**Se quedaron dentro** `Llavero Cala Galdana` (28 €) y `Llavero Cape Nao pequeño` (85 €): pieza artesanal propia, no reventa.

## 5. Cola de revisión: 15 miembros marcados de 486 (3,1 %) en 5 familias

El veto por embedding **marca y nunca elimina**. La prueba es comparativa —un producto de **otra familia propuesta** está más cerca del miembro que su propio peor hermano, por más del margen— y **nunca un umbral absoluto**, porque sobre este corpus las poblaciones de «peor hermano» y «mejor extraño» se solapan.

Parámetro usado: `JPV_FAMILY_VETO_MARGIN = 0.05`. Curva medida sobre los 486: `0,02 → 33 en 18 familias` · **`0,05 → 15 en 5`** · `0,08 → 9 en 2`.

Ocho de los quince son `Colgante estrella de mar`, y ahí está el hallazgo (d).

## 6. Grupos rechazados por la guarda: 4

```
[alianzas]  root_too_short            Alianzas Plata · Alianzas oro
[cadena]    root_is_bare_piece_type   Cadena oro · Cadena plata
[encargos]  root_too_short            Encargos Oro · Encargos plata
[presion]   root_too_short            Presión Oro · Presión plata
```

`Cadena oro` (255 €) y `Cadena plata` (18 €) **sí son joyas**: la guarda las rechazó por un motivo técnico correcto —la raíz queda en el tipo de pieza pelado— y no porque no sean producto. Siguen en el índice y buscables; sólo no forman familia.

## 7. Productos excluidos por la puerta de `piece_type`: 37 (3,1 % de 1.200)

**Cero de los 378 candidatos con sufijo de talla tiene `piece_type` nulo**, así que la regla D9 —el nulo no agrupa con nadie— no costó ni una familia.

La lista se reporta por nombre y no en silencio, y eso destapó que **el nulo significa tres cosas distintas**:

1. **«No es una pieza», y C09 acertó** — velas, palo santo, postales, servicios. Retirados en la sección 4.
2. **«C09 forzó un tipo»** — seis servicios que **sí** tienen `piece_type` porque el vocabulario cerrado no admite «no es una pieza» y el extractor tuvo que elegir algo: `Arreglos oro` → *collar*, `Encargos` → *collar*, `Presión` → *anillo*, `Presión plata (x2)` → *pendientes*. Retirados también.
3. **«Mi vocabulario no la sabe nombrar»** — el hallazgo (c).

---

## Hallazgos de calidad de catálogo

### (a) Las 32 entradas que no eran joyería terminada estaban indexadas

Y por tanto la búsqueda asistida las devolvía. El caso más claro es `Comprobar pureza del oro y preparar el lingote` (75 €): su texto habla de oro y de lingotes, y era un imán para cualquier consulta que mencionara oro. Resuelto en esta ejecución.

### (b) C09 clasifica servicios como joyas porque no puede decir otra cosa

`piece_type.terms` tiene ocho términos y ninguno significa «esto no es una pieza», así que el extractor asigna el más plausible. **Arreglo de raíz pendiente, y es un change propio:** dar a C09 una salida explícita. Mientras no exista, la guarda de raíz degenerada de C18a es lo único que los saca a la luz.

### (c) Nueve joyas sintéticas legítimas que el vocabulario no sabe nombrar

De 160 a 1.300 €: cinco diademas, dos gemelos, un cinturón y una «Joya del Zodiaco». Tienen `piece_type` nulo porque `piece_type.terms` no incluye `diadema`, `gemelos` ni `cinturon` — **incoherencia entre lo que C06b generó y lo que C09 puede expresar**.

**No se han tocado, y es deliberado**: rechazarlas sería empeorar el sistema para tapar una laguna del vocabulario. El arreglo es el contrario —ampliar `piece_type.terms` y reenriquecerlas—, y eso **vuelve a mover el corpus**, así que necesita su propia decisión de cuándo. Anotado como change propio.

### (d) Un producto sintético se coló en una familia real

`Colgante estrella de mar` agrupa siete productos reales y uno sintético, `Colgante Estrella de Mar`, cuyo nombre colisiona con el real pese a que C06b tenía por regla no reutilizar nombres de colección. **El veto lo encontró solo**: ocho de los quince marcados son esta familia, encabezados por márgenes de 0,16. Es la mejor validación que el veto podía tener, y va a la cola de revisión de C18b.

### (e) Una familia real que el agrupador no ve

`Cadena Barbara oro 40 cm / 42 cm / 45 cm` (345–370 €) es una familia de variantes por longitud, y el vocabulario de talla **no tiene escala métrica**. No es un fallo del agrupamiento sino una laguna de vocabulario, del mismo tipo que (c). Anotada.

---

## Vuelta atrás

Documentada en [`design.md`](../../../openspec/changes/add-family-suggestion-and-approval/design.md) y disponible: borrar las familias con `Origin = AiApproved` —cascadea sus miembros por la regla de C07— devolver los 32 perfiles a `Approved`, y resincronizar. El corpus vuelve a su estado anterior. El respaldo `pre-c18a.dump` cubre el caso de que algo salga peor de lo previsto.
