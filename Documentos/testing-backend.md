# Testing Backend - Guía Completa

## Visión General

Stack de testing seleccionado para el backend .NET 10 del sistema de gestión de puntos de venta.

| Componente | Tecnología | Versión |
|------------|------------|---------|
| **Framework de Testing** | xUnit | 2.9.x |
| **Mocking** | Moq | 4.20.x |
| **Assertions** | FluentAssertions | 7.x |
| **CI/CD** | GitHub Actions | - |
| **Tests de Integración** | Testcontainers | 4.x |
| **Generación de Datos** | Bogus | 35.x |

---

## 📚 Índice de Documentación

### Configuración Inicial
| Documento | Descripción |
|-----------|-------------|
| [01 - Configuración](Testing/Backend/01-configuracion.md) | Stack tecnológico, paquetes NuGet, estructura de proyecto y convenciones |

### Tests Unitarios
| Documento | Descripción |
|-----------|-------------|
| [02 - Tests Unitarios](Testing/Backend/02-tests-unitarios.md) | Ejemplos básicos, [Theory], excepciones y generación de datos con Bogus |
| [04 - Mocking EF Core](Testing/Backend/04-mocking-efcore.md) | Mockear DbContext, DbSet, transacciones y uso de InMemory Database |
| [08 - Validaciones](Testing/Backend/08-validaciones.md) | FluentValidation.TestHelper, DataAnnotations y validaciones async |

### Tests de Integración
| Documento | Descripción |
|-----------|-------------|
| [03 - Testcontainers](Testing/Backend/03-testcontainers.md) | PostgreSQL en Docker, fixtures, Respawn y tests de repositorio/API |
| [05 - Autenticación JWT](Testing/Backend/05-autenticacion-jwt.md) | Generar tokens de test, roles, refresh tokens y endpoints protegidos |
| [09 - Archivos y Uploads](Testing/Backend/09-archivos-uploads.md) | Excel con ClosedXML, MockFileSystem y almacenamiento en la nube |

### CI/CD y Calidad
| Documento | Descripción |
|-----------|-------------|
| [06 - GitHub Actions](Testing/Backend/06-github-actions.md) | Workflows, matriz de tests, caché, artifacts y seguridad |
| [07 - Cobertura de Código](Testing/Backend/07-cobertura-codigo.md) | Coverlet, reportes HTML, umbrales mínimos y Codecov |

---

## 🚀 Inicio Rápido

### 1. Crear Proyectos de Test

```bash
# Tests unitarios
cd backend/tests
dotnet new xunit -n Joyeria.UnitTests
cd Joyeria.UnitTests
dotnet add package Moq
dotnet add package FluentAssertions
dotnet add package Bogus

# Tests de integración
cd ..
dotnet new xunit -n Joyeria.IntegrationTests
cd Joyeria.IntegrationTests
dotnet add package Microsoft.AspNetCore.Mvc.Testing
dotnet add package Testcontainers.PostgreSql
dotnet add package Respawn
```

### 2. Ejecutar Tests

```bash
# Todos los tests
dotnet test backend/Joyeria.sln

# Solo unitarios
dotnet test backend/tests/Joyeria.UnitTests

# Con cobertura
dotnet test --collect:"XPlat Code Coverage"

# Filtrar por nombre
dotnet test --filter "FullyQualifiedName~ProductService"
```

---

## 📋 Checklist de Implementación

### Fase 1: Setup Inicial
- [ ] Crear proyecto `Joyeria.UnitTests`
- [ ] Crear proyecto `Joyeria.IntegrationTests`
- [ ] Instalar paquetes NuGet
- [ ] Configurar referencias a proyectos
- [ ] Crear estructura de carpetas

### Fase 2: Tests Unitarios
- [ ] Crear `TestDataBuilder` con Bogus
- [ ] Tests de Services (ProductService, SaleService, etc.)
- [ ] Tests de Validators
- [ ] Tests de mappers/transformaciones

### Fase 3: Tests de Integración
- [ ] Configurar `DatabaseFixture` con Testcontainers
- [ ] Configurar `ApiFixture` con WebApplicationFactory
- [ ] Tests de Repositories
- [ ] Tests de Controllers
- [ ] Tests de autenticación

### Fase 4: CI/CD
- [ ] Crear workflow de GitHub Actions
- [ ] Configurar reporte de tests
- [ ] Configurar cobertura de código
- [ ] Verificar ejecución en PR

### Fase 5: Mantenimiento
- [ ] Añadir badge de tests en README
- [ ] Documentar cómo ejecutar tests localmente
- [ ] Establecer cobertura mínima requerida (70%)
- [ ] Revisar y actualizar tests regularmente

---

## 📖 Convenciones

### Nomenclatura de Tests

```
Método_Escenario_ResultadoEsperado
```

**Ejemplos:**
- `GetProductBySku_WhenProductExists_ShouldReturnProduct`
- `CreateSale_WithInsufficientStock_ShouldThrowException`
- `Login_WithValidCredentials_ShouldReturnToken`

### Estructura AAA

```csharp
[Fact]
public async Task NombreDelTest()
{
    // Arrange - Preparar datos y mocks
    
    // Act - Ejecutar la acción a testear
    
    // Assert - Verificar resultados
}
```

### Helpers compartidos

Viven en `backend/src/JoiabagurPV.Tests/TestHelpers/` y están pensados para reutilizarse, no para copiarse:

| Helper | Para qué sirve |
|---|---|
| `Mothers/` | Constructores de entidades de prueba (patrón *object mother*) |
| `FakeHttpMessageHandler` | Programa respuestas de un servicio externo y **cuenta las peticiones emitidas**, sin red ni contenedor |
| `RecordingLoggerProvider` | Captura eventos de log con su plantilla, propiedades nombradas y *scopes*, para afirmar sobre la traza |
| `RepositoryRoot` | Localiza la raíz del repositorio para leer artefactos externos al backend, como `ai-service/openapi.json` |
| `SchemaAssert` | Lee del catálogo de PostgreSQL la forma que una migración produjo de verdad: tipo y nulabilidad de una columna, longitud máxima, columnas de un índice **en orden**, y regla de borrado de una clave foránea |

Sobre los dos primeros conviene una precisión que ahorra tests engañosos. Al probar un cliente HTTP, **el tipo de excepción no distingue** una condición permanente bien tratada de una mal reintentada: un predicado que reintenta todo acaba lanzando la misma excepción, solo que más tarde. Lo que sí discrimina es el **número de peticiones emitidas**, y por eso `FakeHttpMessageHandler` lo expone. De forma equivalente, una regla que solo vive en el código —por ejemplo, que un texto libre no rebase el nivel `Debug`— desaparece en el primer refactor si nada la afirma: para eso está `RecordingLoggerProvider`.

`SchemaAssert` responde a la misma lógica una capa más abajo. Un test que solo comprueba que *la migración aplica* es teatro: el `TestDatabaseFixture` ya migra antes de cada test de integración, así que no descarta ninguna hipótesis. Lo que merece afirmarse es lo que **falla sin dar error**: una columna que nace `text` en lugar de `jsonb` y no se nota hasta que alguien la consulta meses después, un índice compuesto con las columnas invertidas que sigue existiendo y simplemente deja de servir a su consulta, o una regla de borrado que se quedó en el valor por defecto —que para relaciones obligatorias es en cascada— y el día de la primera purga se lleva por delante datos de negocio. Introducido por C04 y pensado para que las migraciones pendientes escriban sus aserciones en unas pocas líneas: solo contiene las preguntas que hicieron falta, y se amplía cuando haga falta otra.

---

## ⚠️ Estado de la suite: fallos conocidos

*Medido el 2026-08-11 sobre `c04-add-product-search-event-tracking`, con la rama guardada en `git stash` para aislar la línea base. .NET 10, Docker levantado.*

**585 tests, 52 fallos.** Ninguno tiene que ver con el código de aplicación en producción: son defectos de los propios tests y desajustes de dependencias. Se documentan aquí porque, sin este registro, cada persona que ejecuta la suite pierde una hora concluyendo que ha roto algo.

> **Actualización del 2026-08-16, sobre `c08-add-product-ai-profile-entity`.** La suite tiene ahora
> **729 tests** y los fallos se mueven en la banda de **45 a 51** según la ejecución. La cifra
> anterior sigue siendo válida como lo que era —una medición de aquel día sobre aquella rama—,
> pero quien ejecute la suite hoy no reconocerá ni el total ni el número de rojos.
>
> Lo importante de esta segunda medición no es el total, sino algo que la primera no registró:
> **el conjunto de fallos cambia entre ejecuciones idénticas**. Dos pasadas consecutivas sobre el
> mismo commit, sin tocar nada, dieron 48 y 51; dos pasadas posteriores dieron 46 y 48, y los
> nombres no coincidían. `InventoryIntegrationTests` baraja los suyos de una vez a otra.
>
> **Consecuencia práctica:** comparar recuentos no sirve para nada, ni siquiera para decidir que
> algo va mejor. La única comparación válida es **por nombres de test**, y un nombre nuevo en la
> lista solo cuenta como regresión si además falla al ejecutarlo en aislamiento. El procedimiento
> completo, con el caso concreto de tres nombres que parecían regresión y no lo eran, está en
> `openspec/changes/archive/2026-08-16-add-product-ai-profile-entity/qa.md` §1.1.

> **Actualización del 2026-08-17, sobre `c07-add-product-family-entity`.** La suite tiene ahora
> **771 tests** y **44 fallos**. La línea base de ese change, medida antes de escribir una línea de
> código, dio **729 y 49** — dentro de la banda que registró C08.
>
> Esta tercera medición aporta la confirmación que a la anterior le faltaba. Se ejecutó la suite
> completa dos veces sobre la misma rama, con la única diferencia de que entre una y otra el código
> **solo ganó tests**: la primera pasada trajo **tres** nombres nuevos y la segunda **uno distinto**,
> con los conjuntos **disjuntos** y los cuatro verdes al ejecutarlos en aislamiento. Un fallo real no
> desaparece solo. Eso convierte la no determinación del conjunto de fallos de sospecha razonable en
> hecho comprobado, y cierra la pregunta de si comparar recuentos podría servir «al menos para ver
> la tendencia»: no sirve.
>
> El procedimiento y el detalle de las dos pasadas están en
> `openspec/changes/archive/2026-08-17-add-product-family-entity/qa.md` §1.1.

### Por qué se acumularon sin que nadie los viera

Los dos árboles se comportan de forma muy distinta, y esa es la clave:

| Árbol | Tests | Fallos | Desde cuándo se sabe |
|---|---|---|---|
| `UnitTests/` | 315 | **10** | Registrados en el QA de C03 (2026-08-09), **idénticos nombre por nombre** |
| `IntegrationTests/` | 270 | **~42** | **Nunca se habían medido** |

Los de integración necesitan Docker: sin él no se ejecutan, y quien corre la suite en una máquina sin Docker ve 315 tests y 10 fallos, que es exactamente lo que registró C03. En CI sí hay Docker, pero [`test-backend.yml`](../.github/workflows/test-backend.yml) solo se dispara en `push`/`pull_request` a `main` y `develop`, y **todo el Proyecto Final de IA se está construyendo en `ai-eng` y sus ramas de change**. El resultado es un árbol de 270 tests que no se ejecuta ni en local ni en CI durante semanas.

### Los 10 fallos unitarios (estables desde C03)

| Clase | Nº | Causa raíz |
|---|---|---|
| `ImageCompressionServiceTests` | 5 | Umbrales de tamaño comprimido escritos a mano contra una versión anterior de ImageSharp; la actual codifica distinto y produce bytes de más |
| `QrCodeServiceTests` | 2 | `MissingMethodException` sobre `ImageSharp.Image.Load` — **incompatibilidad binaria**: `PdfSharpCore` se compiló contra otra API. Y `PdfSharpCore` rechaza guardar un PDF sin páginas |
| `InventoryServiceTests` | 2 | Expectativas de Moq sobre `BeginTransactionAsync` / `RollbackTransactionAsync` que el servicio ya no invoca |
| `ExcelImportServiceTests` | 1 | La validación devuelve `false` donde el test espera `true` |

Los dos primeros grupos son **deriva de dependencias**, no lógica rota; los dos últimos son tests que se quedaron atrás respecto al código.

### Los ~42 fallos de integración

| Familia | Nº aprox. | Causa raíz |
|---|---|---|
| «Se esperaba 401 y llegó 200 / 403 / 201» | 16 | El `HttpClient` compartido de la clase de test es el que hace los `login`, así que **arrastra sus cookies**: la llamada «anónima» no lo es. Se arregla pidiendo un cliente nuevo a la factoría |
| `Cannot create a DbSet for 'TestEntity'` | 4 | `RepositoryTests` usa una entidad que no está en el modelo del contexto |
| `22001: value too long for character varying(20)` | 4 | Las *object mothers* generan datos con Bogus y el teléfono generado no siempre cabe en `PointOfSale.Phone`. **Es la única familia genuinamente no determinista**, y explica que dos ejecuciones del mismo código den recuentos distintos |
| Varios | resto | Concurrencia en venta de última unidad, validaciones de importación, un 500 y un 400 puntuales |

### Cómo distinguir una regresión propia

**Por nombres, no por número.** El recuento varía entre ejecuciones por la familia de Bogus:

```bash
git stash push -u          # guardar el trabajo en curso
dotnet test JoiabagurPV.Tests/JoiabagurPV.Tests.csproj
git stash pop              # recuperarlo
# el cambio está limpio si el CONJUNTO DE NOMBRES que falla es el mismo
```

### Qué haría falta para cerrarlo

No es trabajo de un change de funcionalidad y **merece uno propio**. En orden de rentabilidad: extender el disparador de CI a las ramas de trabajo, para que esto deje de crecer en silencio; arreglar la familia de las cookies, que son 16 tests con una sola corrección; fijar los datos generados que chocan con límites de columna; y alinear ImageSharp con lo que `PdfSharpCore` espera.

Dos de estas familias se toparon y se corrigieron **dentro de los tests nuevos** de C04, así que el patrón de arreglo ya está escrito en `AiSearchEventsControllerTests`.

---

## 🔗 Recursos Externos

- [xUnit Documentation](https://xunit.net/docs/getting-started/netcore/cmdline)
- [FluentAssertions Documentation](https://fluentassertions.com/introduction)
- [Moq Quickstart](https://github.com/moq/moq4/wiki/Quickstart)
- [ASP.NET Core Integration Tests](https://learn.microsoft.com/en-us/aspnet/core/test/integration-tests)
- [Testcontainers .NET](https://dotnet.testcontainers.org/)
- [Unit Testing Best Practices](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices)

---

## 🎯 Conclusión

Esta combinación de herramientas ofrece:

- ✅ **Productividad**: Sintaxis clara y herramientas bien documentadas
- ✅ **Confiabilidad**: Tests reproducibles con contenedores Docker
- ✅ **Escalabilidad**: Fácil de extender y mantener
- ✅ **Integración**: Compatible con GitHub Actions y free-tier
- ✅ **Comunidad**: Amplio soporte y ejemplos disponibles
