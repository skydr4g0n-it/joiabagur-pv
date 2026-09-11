# C25 — barrido de la fusión por rama (fase A)

La regla que decide se escribió **antes** de medir y está fechada en D14 del `design.md`; el código la aplica en `evals/sweep.py`. La lectura que **decide** es `nuevas` —las 40 consultas que ninguna calibración ha visto—; `ajuste` se publica como **diagnóstico de contaminación** y no veta.

La rejilla es **de una dimensión**, sobre `rho = w_vec / w_lex`, porque sólo el cociente cambia el orden: escalar los dos pesos lo preserva. `k` y la profundidad se mueven juntos, por la regla de C21 de que una rama más profunda mantiene más cola votando. La banda útil es estrecha —`rho ∈ [0,9 ; 1,1]`— y la rejilla de C24 tenía **un solo punto** dentro, que es por qué su óptimo parecía un filo de cuchillo.

La columna `cobertura` es la segunda fila candidata: la regla **continua** no tiene parámetro y es la adoptada; la **binaria** lleva una `α` declarada y entra para que esa elección sea falsable en vez de supuesta.

| rho | k / profundidad | cobertura | nDCG@5 global | sólo ajuste | **nuevas (decide)** |
|---:|---:|---|---:|---:|---:|
| 0.6 | 40/40 | binary | 0.669 | 0.932 | **0.616** |
| 0.6 | 60/60 | binary | 0.667 | 0.942 | **0.613** |
| 0.8 | 40/40 | binary | 0.667 | 0.936 | **0.613** |
| 0.8 | 60/60 | binary | 0.663 | 0.934 | **0.609** |
| 0.9 | 40/40 | binary | 0.667 | 0.936 | **0.613** |
| 0.9 | 60/60 | binary | 0.663 | 0.936 | **0.608** |
| 0.95 | 40/40 | binary | 0.666 | 0.930 | **0.613** |
| 0.95 | 60/60 | binary | 0.663 | 0.936 | **0.608** |
| 1.0 | 40/40 | binary | 0.661 | 0.898 | **0.613** |
| 1.0 | 60/60 | binary | 0.663 | 0.936 | **0.608** |
| 1.05 | 40/40 | binary | 0.656 | 0.870 | **0.613** |
| 1.05 | 60/60 | binary | 0.663 | 0.936 | **0.608** |
| 1.1 | 40/40 | binary | 0.651 | 0.853 | **0.610** |
| 1.1 | 60/60 | binary | 0.661 | 0.936 | **0.606** |
| 1.25 | 40/40 | binary | 0.651 | 0.857 | **0.610** |
| 1.25 | 60/60 | binary | 0.661 | 0.940 | **0.605** |
| 0.6 | 40/40 | continuous | 0.669 | 0.932 | **0.616** |
| 0.6 | 60/60 | continuous | 0.667 | 0.942 | **0.613** |
| 0.8 | 40/40 | continuous | 0.667 | 0.936 | **0.613** |
| 0.8 | 60/60 | continuous | 0.663 | 0.934 | **0.609** |
| 0.9 | 40/40 | continuous | 0.667 | 0.936 | **0.613** |
| 0.9 | 60/60 | continuous | 0.663 | 0.936 | **0.608** |
| 0.95 | 40/40 | continuous | 0.666 | 0.930 | **0.613** |
| 0.95 | 60/60 | continuous | 0.663 | 0.936 | **0.608** |
| 1.0 | 40/40 | continuous | 0.661 | 0.898 | **0.613** |
| 1.0 **(vigente)** | 60/60 | continuous | 0.663 | 0.936 | **0.608** |
| 1.05 | 40/40 | continuous | 0.656 | 0.870 | **0.613** |
| 1.05 | 60/60 | continuous | 0.663 | 0.936 | **0.608** |
| 1.1 | 40/40 | continuous | 0.651 | 0.853 | **0.610** |
| 1.1 | 60/60 | continuous | 0.661 | 0.936 | **0.606** |
| 1.25 | 40/40 | continuous | 0.651 | 0.857 | **0.610** |
| 1.25 | 60/60 | continuous | 0.661 | 0.940 | **0.605** |

## Veredicto de la regla

- Configuración vigente: **rho=1.0 (w_lex=0.500 w_vec=0.500) k=60 depth=60 cobertura=continuous** → nDCG@5 (new) 0.608
- Mejor del barrido: **rho=0.6 (w_lex=0.625 w_vec=0.375) k=40 depth=40 cobertura=continuous** → nDCG@5 (new) 0.616
- Deltas por lectura: global +0.006, tuning -0.004, new +0.008
- Lectura que **decide**: `new`. `tuning` se publica como **diagnóstico de contaminación** (-0.004) y no veta.
- Peor categoría: descripcion-sin-anclaje -0.011, fuera-de-dominio +0.000, lexico-exacto +0.000
- **Veredicto: NO se mueve el default** — la mejora en `new` es +0.008, por debajo del margen acordado de 0.05; con un intervalo de ±0,13 sobre la porción real, una diferencia así no se distingue del ruido de anotación
