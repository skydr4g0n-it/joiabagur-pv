# Guía completa: Instalación de uv y creación de un proyecto desde cero (Windows 11)

Creada: 17 de abril de 2026 19:01
Módulo: M1. Fundamentos de productos con IA (https://app.notion.com/p/M1-Fundamentos-de-productos-con-IA-345ea9ca03c480c28067c95e73566115?pvs=21)
Sesión: S1. LLMs y setup de entorno de trabajo (https://app.notion.com/p/S1-LLMs-y-setup-de-entorno-de-trabajo-345ea9ca03c48076a253ffecb6e18093?pvs=21)

# 1. 🔧 Requisitos previos

---

### 1.1 Tener Python instalado

Comprueba si ya lo tienes:

```bash
python --version
```

o

```bash
py --version
```

### Si NO está instalado:

1. Descarga Python desde: [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
2. Durante la instalación:
    - ⚠️ Marca **"Add Python to PATH"**
    - Instalación estándar

---

## 2. ⚡ Instalación de `uv`

### Opción recomendada

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Verificar instalación

```bash
uv --version
```

---

## 3. 📁 Crear un proyecto desde cero

```bash
mkdir mi-proyecto-ai
cd mi-proyecto-ai
```

```bash
uv init
```

---

# 🔍 4. `pyproject.toml` (núcleo del proyecto)

## 4.1 ¿Qué es?

Es el **archivo estándar moderno de configuración en Python**. Sustituye a:

- `requirements.txt`
- `setup.py`
- `setup.cfg`

👉 Centraliza toda la configuración del proyecto.

---

## 4.2 Ejemplo típico

```toml
[project]
name = "mi-proyecto-ai"
version = "0.1.0"
description = "Proyecto de AI"
dependencies = [
    "numpy>=1.26.0",
    "pandas>=2.0.0"
]

[tool.uv]
# Config específica de uv (opcional)
```

---

## 4.3 Cómo se lee

- `[project]` → metadata del proyecto
- `dependencies` → dependencias directas (las que tú defines)
- Versionado tipo:
    - `>=` mínimo aceptado
    - `==` versión exacta (no recomendado salvo casos críticos)

---

## 4.4 Cómo lo usa `uv`

Cuando ejecutas:

```bash
uv add numpy
```

👉 `uv`:

1. Añade `numpy` a `pyproject.toml`
2. Resuelve dependencias
3. Genera/actualiza `uv.lock`
4. Instala paquetes

---

## 4.5 Idea clave

- `pyproject.toml` → **intención del desarrollador**
- `uv.lock` → **estado exacto reproducible**

---

# 🔒 5. `uv.lock` (reproducibilidad total)

## 5.1 ¿Qué es?

Archivo generado automáticamente con:

```bash
uv add ...
uv sync
```

---

## 5.2 ¿Qué contiene?

- Versiones exactas de todas las dependencias (directas + indirectas)
- Hashes de paquetes
- Resolución completa del árbol de dependencias

Ejemplo simplificado:

```toml
[[package]]
name = "numpy"
version = "1.26.4"

[[package]]
name = "pandas"
version = "2.2.0"
```

---

## 5.3 Función

👉 Garantizar que:

- Tu entorno = entorno de tu compañero
- Tu entorno = producción

---

## 5.4 Cuándo se genera

- `uv add`
- `uv sync`
- `uv lock` (explícito)

---

## 5.5 Regla importante

✔️ **Siempre subir `uv.lock` al repositorio**

---

# 🧪 6. Entornos virtuales (`venv`) con `uv`

---

## 6.1 Crear entorno

```bash
uv venv
```

Genera:

```
.venv/
├── Scripts/
├── Lib/
├── pyvenv.cfg
```

---

## 6.2 ¿Cómo detecta `uv` el entorno?

`uv` sigue esta lógica:

1. Busca `.venv` en el directorio actual
2. Si existe → lo usa automáticamente
3. Si no → puede crearlo o usar sistema global

👉 No necesitas hacer `activate`

---

## 6.3 Cambiar entre entornos virtuales

### Opción 1 (recomendada)

- Cambiar de carpeta de proyecto

### Opción 2 (manual)

```bash
uv run --python path_al_entorno script.py
```

---

## 6.4 ¿Se pueden tener varios entornos en un proyecto?

Sí, pero **no es buena práctica**.

Ejemplo:

```
.venv/
.venv-dev/
.venv-gpu/
```

👉 Problema:

- Confusión
- Errores de dependencia

✔️ Recomendación:

- 1 entorno por proyecto

---

## 6.5 ¿Cómo saber qué entorno estás usando?

En terminal:

```bash
where python
```

o

```bash
uv run python -c "import sys; print(sys.executable)"
```

---

## 6.6 Gestión de versión de Python

`uv` puede usar versiones específicas:

```bash
uv venv --python 3.11
```

👉 Esto fija la versión del entorno

---

## 6.7 Buenas prácticas de naming

✔️ Usar siempre:

```
.venv
```

❌ Evitar:

- `env`
- `venv_project`
- nombres inconsistentes

Motivo:

- herramientas lo detectan automáticamente (`uv`, VSCode, etc.)

---

## 6.8 ¿Ocupan mucho espacio?

### Sin Docker:

- Cada entorno: ~100MB – 500MB (dependiendo de librerías)
- ML/AI: puede subir a >1GB

### Con Docker:

- Imagen completa: varios GB fácilmente

👉 Conclusión:

- Sí, ocupan espacio, pero es normal en AI

---

## 6.9 ¿Se pueden dockerizar?

Sí, y es práctica estándar.

Pero:

👉 **No se copia `.venv` al contenedor**

Se hace:

```docker
RUN pip install ...
```

o con `uv`:

```docker
RUN uv sync
```

👉 El contenedor recrea el entorno desde `uv.lock`

---

# 🔁 7. Sincronización (`uv sync`)

---

## 7.1 ¿Qué hace?

```bash
uv sync
```

👉 Sincroniza el entorno virtual con `uv.lock`

- Instala lo que falta
- Elimina lo que sobra
- Asegura consistencia total

---

## 7.2 Cuándo usarlo

### Caso 1 — Clonas repo

```bash
git clone ...
cd proyecto
uv sync
```

---

### Caso 2 — Cambios en dependencias

Si alguien modifica `uv.lock`:

```bash
git pull
uv sync
```

---

### Caso 3 — Entorno roto

- conflictos
- paquetes inconsistentes

👉 `uv sync` lo limpia

---

## 7.3 Ejemplo práctico

### Escenario

Tienes:

```toml
dependencies = ["numpy"]
```

Otro dev añade:

```bash
uv add pandas
```

Te llega el cambio:

```bash
git pull
uv sync
```

👉 Resultado:

- Se instala `pandas`
- Se ajusta todo el entorno

---

## 7.4 Cuándo NO usarlo

❌ No hace falta tras cada `uv add`

❌ No sustituye a `uv add`

---

## 7.5 Idea clave

- `uv add` → modifica dependencias
- `uv sync` → aplica estado exacto

---

# 🚀 8. Flujo de trabajo recomendado

```bash
uv init
uv venv
uv add numpy pandas
uv run main.py
```

En equipo:

```bash
git pull
uv sync
```

---

# 📌 9. Conclusión técnica

- `pyproject.toml` → define dependencias (alto nivel)
- `uv.lock` → fija versiones exactas (bajo nivel)
- `.venv` → entorno aislado reproducible
- `uv sync` → asegura consistencia total

👉 Esto es exactamente el modelo moderno tipo:

- Node.js → `package.json` + `package-lock.json`
- Rust → `Cargo.toml` + `Cargo.lock`

---

Si quieres, el siguiente paso lógico es montar un **proyecto real de AI Engineer** (entrenamiento + API + tracking) estructurado correctamente con `uv`.