# C24 — barrido direccional del peso de la rama vectorial y de la profundidad

La regla que decide se escribió **antes** de medir; ver `evals/sweep.py`. El barrido es direccional: la rúbrica que fijó los pesos vigentes es la función objetivo de la rama léxica, así que infravalora la vectorial por construcción y el óptimo verdadero no puede estar por debajo del valor en vigor.

| wC | profundidad | nDCG@5 global | sólo ajuste | sólo nuevas |
|---:|---:|---:|---:|---:|
| 0.33 | 40 | 0.607 | 0.942 | 0.540 |
| 0.33 **(vigente)** | 60 | 0.603 | 0.942 | 0.535 |
| 0.5 | 40 | 0.630 | 0.893 | 0.577 |
| 0.5 | 60 | 0.632 | 0.931 | 0.572 |
| 0.75 | 40 | 0.649 | 0.841 | 0.611 |
| 0.75 | 60 | 0.659 | 0.924 | 0.606 |
| 1.0 | 40 | 0.653 | 0.853 | 0.612 |
| 1.0 | 60 | 0.659 | 0.918 | 0.608 |
| 1.5 | 40 | 0.640 | 0.793 | 0.610 |
| 1.5 | 60 | 0.639 | 0.809 | 0.605 |
| 2.0 | 40 | 0.639 | 0.781 | 0.611 |
| 2.0 | 60 | 0.639 | 0.802 | 0.606 |

## Veredicto de la regla

- Configuración vigente: **wC=0.33 depth=60** → nDCG@5 0.603
- Mejor del barrido: **wC=1.0 depth=60** → nDCG@5 0.659
- Deltas por lectura: global +0.057, tuning -0.024, new +0.073
- Peor categoría: sinonimos -0.039, materiales -0.010, variante-talla -0.004
- **Veredicto: NO se mueve el default** — el signo no es el mismo en las tres lecturas: ['tuning'] no mejora. Un resultado que sólo se sostiene en el conjunto de ajuste es sobreajuste, y encontrarlo es el trabajo
