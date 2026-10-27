# Guía de Administración del Modelo de IA

> **Retirado (2026-10-27):** El reconocimiento de productos por foto ya no forma parte del sistema. Esta guía se conserva solo como referencia histórica.

## Estado actual

- No existe la pantalla **Modelo de IA** ni la ruta `/admin/ai-model` en la aplicación.
- El sistema no muestra alertas de salud del modelo al iniciar sesión.
- Las ventas se registran de forma **manual**, por **escaneo de código** o con **carrito**.
- La API `GET /api/image-recognition/*` responde **410 Gone** con el código `image_recognition_withdrawn`.

## Datos y esquema

Las tablas y archivos de modelos o embeddings (`ModelMetadata`, `ProductPhotoEmbedding`, etc.) pueden seguir existiendo en la base de datos por compatibilidad, pero la aplicación actual **no** los utiliza para inferencia ni entrenamiento.

Para el flujo operativo vigente, consulte [ventas-registro.md](ventas-registro.md).
