# C26 — rebanada de sustitutos

| Procedencia | Valor |
|---|---|
| golden_set_version | `1:89c178e55603` |
| config_id | `c26-substitutes-slice` |
| index_set_hash | `051a6b06021efc3fb18891ffc7acfa2c6e3499f161aa81e9e96dd061233e073b` |
| embedding_model_version_key | `None` |
| git_sha | `b6fe67c50994f64609fa5ce3c541b7684b81bc5f+dirty` |
| fusion_mode | `none` |

5 consultas ancladas · 11 pesos · **cero llamadas al proveedor**.

| `w_size` | nDCG@5 | nDCG@5 binario | Recall@5 | P@3 | MRR | unjudged@5 |
|---:|---:|---:|---:|---:|---:|---:|
| `0` | 0.7414 | 1.0000 | 0.4241 | 1.0000 | 1.0000 | 0.0000 |
| `0.02` | 0.7529 | 1.0000 | 0.4241 | 1.0000 | 1.0000 | 0.0000 |
| `0.04` | 0.8199 | 1.0000 | 0.4241 | 1.0000 | 1.0000 | 0.0000 |
| `0.05` | 0.8453 | 1.0000 | 0.4241 | 1.0000 | 1.0000 | 0.0000 |
| `0.06` | 0.8504 | 1.0000 | 0.4241 | 1.0000 | 1.0000 | 0.0000 |
| `0.07` | 0.8713 | 0.9738 | 0.4135 | 1.0000 | 1.0000 | 0.0000 |
| `0.075` | 0.8785 | 0.9738 | 0.4135 | 1.0000 | 1.0000 | 0.0000 |
| `0.08` | 0.8785 | 0.9738 | 0.4135 | 1.0000 | 1.0000 | 0.0000 |
| `0.1` | 0.8667 | 0.9398 | 0.4035 | 0.9333 | 1.0000 | 0.0000 |
| `0.12` | 0.8667 | 0.9398 | 0.4035 | 0.9333 | 1.0000 | 0.0000 |
| `0.2` | 0.7982 | 0.8179 | 0.2535 | 0.8000 | 1.0000 | 0.0000 |

## nDCG@5 por consulta

| `w_size` | q49 | q50 | q51 | q52 | q72 |
|---:|---:|---:|---:|---:|---:|
| `0` | 0.5162 | 0.5182 | 0.7600 | 1.0000 | 0.9125 |
| `0.02` | 0.5284 | 0.5635 | 0.7600 | 1.0000 | 0.9125 |
| `0.04` | 0.6671 | 0.7600 | 0.7600 | 1.0000 | 0.9125 |
| `0.05` | 0.6671 | 0.8869 | 0.7600 | 1.0000 | 0.9125 |
| `0.06` | 0.6671 | 0.9125 | 0.7600 | 1.0000 | 0.9125 |
| `0.07` | 0.7713 | 0.9125 | 0.7600 | 1.0000 | 0.9125 |
| `0.075` | 0.8077 | 0.9125 | 0.7600 | 1.0000 | 0.9125 |
| `0.08` | 0.8077 | 0.9125 | 0.7600 | 1.0000 | 0.9125 |
| `0.1` | 0.7920 | 0.8688 | 0.7600 | 1.0000 | 0.9125 |
| `0.12` | 0.7920 | 0.8688 | 0.7600 | 1.0000 | 0.9125 |
| `0.2` | 0.7920 | 0.8688 | 0.7600 | 0.6577 | 0.9125 |

## El recorrido y la decisión

- **Máximo de nDCG@5 graduado:** `0.075` (0.8785).
- **Guardarraíl** (lectura binaria, Recall@5 y P@3 en su máximo): se mantiene hasta `0.06` inclusive y se rompe a partir de ahí.
- Las dos lecturas **discrepan**, y `criterion.md` dice que eso es un hallazgo y se publica: el graduado premia `0.075` (+0.0281), pero ahí la lectura binaria cae 0.0262 y Recall@5 0.0105: entra un documento de grado 0 en un top-5. Gana el guardarraíl.

Configuraciones: `c26-substitutes-w0`, `c26-substitutes-w0.02`, `c26-substitutes-w0.04`, `c26-substitutes-w0.05`, `c26-substitutes-w0.06`, `c26-substitutes-w0.07`, `c26-substitutes-w0.075`, `c26-substitutes-w0.08`, `c26-substitutes-w0.1`, `c26-substitutes-w0.12`, `c26-substitutes-w0.2`.

> Mide la calidad del sustituto **dado el producto origen correcto**. La cadena completa «texto del operador → producto → sustitutos» es de C32 y no se mide aquí.
