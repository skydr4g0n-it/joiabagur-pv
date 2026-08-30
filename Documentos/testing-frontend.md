# Testing Frontend - Guía Completa

## Visión General

Stack de testing seleccionado para el frontend React 19 + TypeScript + Vite del sistema de gestión de puntos de venta.

| Componente | Tecnología | Versión |
|------------|------------|---------|
| **Test Runner** | Vitest | 2.x |
| **Testing de Componentes** | React Testing Library | 16.x |
| **Simulación de Usuario** | @testing-library/user-event | 14.x |
| **Matchers DOM** | @testing-library/jest-dom | 6.x |
| **Mocking de API** | MSW (Mock Service Worker) | 2.x |
| **Tests E2E** | Playwright | 1.x |
| **Entorno DOM** | jsdom | 25.x |

---

## 📚 Índice de Documentación

### Configuración Inicial
| Documento | Descripción |
|-----------|-------------|
| [01 - Configuración](Testing/Frontend/01-configuracion.md) | Stack tecnológico, instalación, estructura de proyecto y convenciones |

### Tests Unitarios y de Componentes
| Documento | Descripción |
|-----------|-------------|
| [02 - Tests Unitarios](Testing/Frontend/02-tests-unitarios.md) | Tests de hooks, utilities, helpers y funciones puras |
| [03 - Tests de Componentes](Testing/Frontend/03-tests-componentes.md) | React Testing Library, queries, user events, formularios (React Hook Form + Zod) y accesibilidad |
| [04 - Mocking de API](Testing/Frontend/04-mocking-api.md) | MSW handlers, escenarios de error, interceptores y estados de carga |

### Tests End-to-End
| Documento | Descripción |
|-----------|-------------|
| [05 - Tests E2E](Testing/Frontend/05-tests-e2e.md) | Playwright, navegación, formularios, autenticación y multi-navegador |

### CI/CD y Calidad
| Documento | Descripción |
|-----------|-------------|
| [06 - GitHub Actions](Testing/Frontend/06-github-actions.md) | Workflows, caché de dependencias, artifacts y reportes |
| [07 - Cobertura de Código](Testing/Frontend/07-cobertura-codigo.md) | Configuración de coverage, umbrales mínimos y reportes HTML |

---

## 🚀 Inicio Rápido

### 1. Instalar Dependencias

```bash
cd frontend

# Vitest y Testing Library
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom

# MSW para mocking de API
npm install -D msw

# Playwright para E2E
npm install -D @playwright/test
npx playwright install
```

### 2. Configurar Vitest

**vite.config.ts**
```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: ['node_modules/', 'src/test/'],
    },
  },
})
```

**src/test/setup.ts**
```typescript
import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Limpieza automática después de cada test
afterEach(() => {
  cleanup()
})
```

### 3. Ejecutar Tests

```bash
# Tests unitarios y de componentes
npm run test

# Tests en modo watch
npm run test:watch

# Tests con cobertura
npm run test:coverage

# Tests E2E con Playwright
npm run test:e2e

# Tests E2E con UI de Playwright
npm run test:e2e:ui
```

### 4. Scripts en package.json

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:ui": "vitest --ui",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:headed": "playwright test --headed"
  }
}
```

---

## 📁 Estructura de Proyecto

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/
│   │   │   ├── button.tsx
│   │   │   └── button.test.tsx          # Test junto al componente
│   │   └── layouts/
│   ├── hooks/
│   │   ├── use-auth.ts
│   │   └── use-auth.test.ts             # Test junto al hook
│   ├── services/
│   │   ├── api.service.ts
│   │   └── api.service.test.ts
│   ├── lib/
│   │   ├── utils.ts
│   │   └── utils.test.ts
│   └── test/
│       ├── setup.ts                      # Setup global de Vitest
│       ├── mocks/
│       │   ├── handlers.ts               # MSW handlers
│       │   └── server.ts                 # MSW server
│       ├── utils/
│       │   ├── render.tsx                # Custom render con providers
│       │   └── test-data.ts              # Factories de datos de test
│       └── __fixtures__/
│           └── products.json             # Datos de prueba
├── e2e/
│   ├── auth.spec.ts                      # Tests E2E de autenticación
│   ├── products.spec.ts                  # Tests E2E de productos
│   ├── sales.spec.ts                     # Tests E2E de ventas
│   └── fixtures/
│       └── test-user.json
├── playwright.config.ts
├── vite.config.ts
└── package.json
```

---

## 📋 Checklist de Implementación

### Fase 1: Setup Inicial
- [ ] Instalar dependencias de testing
- [ ] Configurar Vitest en `vite.config.ts`
- [ ] Crear archivo `src/test/setup.ts`
- [ ] Configurar scripts en `package.json`
- [ ] Crear estructura de carpetas de test

### Fase 2: Tests Unitarios
- [ ] Crear custom render con providers
- [ ] Tests de hooks personalizados (`use-auth`, `use-menu`, etc.)
- [ ] Tests de utilities (`lib/utils.ts`, `lib/helpers.ts`)
- [ ] Tests de servicios de API

### Fase 3: Tests de Componentes
- [ ] Configurar MSW handlers base
- [ ] Tests de componentes UI básicos (Button, Input, Select)
- [ ] Tests de componentes de formulario
- [ ] Tests de componentes con estado
- [ ] Tests de accesibilidad (a11y)

### Fase 4: Tests E2E
- [ ] Configurar Playwright (`playwright.config.ts`)
- [ ] Tests de flujo de autenticación
- [ ] Tests de CRUD de productos
- [ ] Tests de registro de ventas
- [ ] Tests responsive (móvil/desktop)

### Fase 5: CI/CD
- [ ] Crear workflow de GitHub Actions
- [ ] Configurar caché de dependencias
- [ ] Configurar reporte de tests
- [ ] Configurar cobertura de código
- [ ] Verificar ejecución en PR

### Fase 6: Mantenimiento
- [ ] Añadir badge de tests en README
- [ ] Documentar cómo ejecutar tests localmente
- [ ] Establecer cobertura mínima requerida (70%)
- [ ] Revisar y actualizar tests regularmente

---

## 📖 Convenciones

### Nomenclatura de Tests

```
describe('NombreComponente/Hook/Función', () => {
  it('should [comportamiento esperado] when [condición]', () => {})
})
```

**Ejemplos:**
- `should render product name when product is provided`
- `should call onSubmit when form is valid`
- `should show error message when API returns 401`
- `should disable button when loading is true`

### Estructura de Test

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

describe('ProductCard', () => {
  it('should render product information correctly', async () => {
    // Arrange - Preparar datos y renderizar
    const product = { id: '1', name: 'Anillo Oro', sku: 'ANI-001' }
    render(<ProductCard product={product} />)

    // Act - Ejecutar acciones (si las hay)
    // En este caso no hay acciones

    // Assert - Verificar resultados
    expect(screen.getByText('Anillo Oro')).toBeInTheDocument()
    expect(screen.getByText('ANI-001')).toBeInTheDocument()
  })

  it('should call onClick when card is clicked', async () => {
    // Arrange
    const user = userEvent.setup()
    const handleClick = vi.fn()
    const product = { id: '1', name: 'Anillo Oro', sku: 'ANI-001' }
    render(<ProductCard product={product} onClick={handleClick} />)

    // Act
    await user.click(screen.getByRole('article'))

    // Assert
    expect(handleClick).toHaveBeenCalledWith(product)
  })
})
```

### Queries de Testing Library (Orden de Prioridad)

| Prioridad | Query | Uso |
|-----------|-------|-----|
| 1️⃣ | `getByRole` | Elementos accesibles (botones, links, etc.) |
| 2️⃣ | `getByLabelText` | Inputs de formulario |
| 3️⃣ | `getByPlaceholderText` | Inputs sin label visible |
| 4️⃣ | `getByText` | Texto visible |
| 5️⃣ | `getByDisplayValue` | Valor actual de inputs |
| 6️⃣ | `getByAltText` | Imágenes |
| 7️⃣ | `getByTitle` | Elementos con title |
| 8️⃣ | `getByTestId` | Último recurso (data-testid) |

---

## ⚠️ Estado de la suite: fallos conocidos

*Medido el 2026-08-29 sobre `c16-add-frontend-assisted-search-panel`, con el árbol de trabajo idéntico a `HEAD` para aislar la línea base. Node + Vitest 4 + jsdom.*

**482 tests, 118 fallos, en 17 de los 40 ficheros.** Duración: 252 s. Ninguno tiene que ver con el código de producción: son defectos de los propios tests, mocks incompletos y aserciones que se quedaron atrás cuando la interfaz cambió. Se documentan aquí por la misma razón que los del backend — sin este registro, cada persona que ejecuta la suite pierde una hora concluyendo que ha roto algo — y por una razón más, que el backend no tiene.

> **`vitest` sale con código 0 si canalizas su salida.** `npm run test | tail` devuelve el código de `tail`, no el de la suite. Un prompt verde no significa nada: hay que leer la línea de resumen.

> **Actualización del 2026-08-30, sobre `c17-add-ai-service-deployment`.** La suite tiene ahora **529 tests, 116 fallos, en 15 de los 44 ficheros** en la línea base, y **533, 113 y 14 de 45** al cierre del change. Los cuatro tests de más son los de `pages/dashboard/ai-service-status.test.tsx`, los cuatro verdes.
>
> La comparación por nombres salió **subconjunto estricto**: ni un fallo nuevo, y **tres que dejaron de fallar** sin que nadie tocara sus ficheros — los tres de `pages/sales/__tests__/assisted.test.tsx`, conocidos por ser dependientes del orden. Es la segunda vez que se observa el mismo fenómeno tras el de C16, y refuerza la regla de esta misma sección: el número no sirve, el conjunto de nombres sí.

### La comparación válida es por nombres, igual que en el backend

```powershell
# Línea base, antes de tocar nada
npm run test

# Después
npm run test
```

Tu cambio está limpio si el **conjunto de nombres** que falla es el mismo, no si coincide el número. Y el número tampoco es estable aquí: añadir ficheros de test desplaza el orden de ejecución, y con él un puñado de fallos dependientes del orden. En la pasada de C16, con 43 tests nuevos añadidos, **cinco tests que fallaban dejaron de fallar** sin que nadie tocara sus ficheros.

### Los 17 ficheros en rojo

| Fichero | Fallos | Causa dominante |
|---|---|---|
| `pages/products/edit.test.tsx` | **27 / 27** | A · `useAuth must be used within an AuthProvider` |
| `services/__tests__/ml-edge-cases.test.ts` | 23 / 27 | B · mock de TensorFlow.js incompleto |
| `services/__tests__/image-recognition.service.test.ts` | 15 / 40 | B + C |
| `pages/products/components/product-photo-upload.test.tsx` | 12 / 35 | E · aserciones desactualizadas |
| `pages/sales/__tests__/new.test.tsx` | **11 / 11** | A · `useCart must be used within a CartProvider` |
| `pages/sales/__tests__/new-image.test.tsx` | 8 / 17 | A · `useCart` |
| `pages/payment-methods/payment-methods.test.tsx` | 4 / 13 | E |
| `services/__tests__/model-training.service.test.ts` | 4 / 10 | C + `canvas.addEventListener is not a function` |
| `pages/products/__tests__/edit.test.tsx` | 4 / 4 | D · `vi.mock` sin factoría |
| `pages/products/create.test.tsx` | 2 / 25 | C · timeout |
| `services/product.service.test.ts` | 2 / 10 | D |
| `pages/points-of-sale/points-of-sale.test.tsx` | 1 / 17 | C |
| `pages/sales/__tests__/sales-index.test.tsx` | 1 / 3 | E · `Found multiple elements` |
| `pages/sales/__tests__/scan.test.tsx` | 1 / 2 | E |
| `pages/users/users.test.tsx` | 1 / 12 | C |
| `services/auth.service.test.ts` | 1 / 8 | E |
| `services/payment-method.service.test.ts` | 1 / 11 | E |

### Las cinco causas raíz

**A · La página se renderiza sin su proveedor de contexto.** La más numerosa: alrededor de un tercio del rojo. Renderizar un componente de página arrastra todos los contextos que consume, y si falta uno el hook lanza. `new.test.tsx` falla **entero** por `useCart`, y `products/edit.test.tsx` **entero** por `useAuth`. No es un fallo de la aplicación: es que el test monta el componente desnudo.

*Cómo se escribe bien:* envolver en el proveedor real, o mockear el hook. [`pages/sales/__tests__/cart.test.tsx`](../frontend/src/pages/sales/__tests__/cart.test.tsx) —que está en verde— es el fichero a copiar: mockea `@/providers/cart-provider` con un objeto de estado que el test controla.

**B · El mock global de TensorFlow.js se quedó corto.** `src/test/setup.ts` mockea `@tensorflow/tfjs` con `createTensorFlowMock()`, y ese doble no exporta todo lo que el código bajo prueba usa: `No "memory" export is defined on the "@tensorflow/tfjs" mock`. Afecta a los dos ficheros de aprendizaje automático.

**C · Timeouts de 10 s.** 27 ocurrencias, y en su mayoría **consecuencia** de A y B: cuando el render lanza, el `waitFor` que lo sigue espera algo que nunca va a aparecer y agota el reloj. Perseguir el timeout suele ser perseguir el síntoma.

**D · `vi.mock` sin factoría deja los miembros en `undefined`.** `vi.mock('@/services/product.service')` sin segundo argumento produce un módulo cuyos miembros son `undefined`, y el test revienta con `Cannot read properties of undefined (reading 'getProduct')`. Hay que pasar la factoría, o usar `vi.mocked(...)` sobre un mock automático que sí exista.

**E · Aserciones que la interfaz dejó atrás.** `Unable to find an element with the text …`, `Found multiple elements …`, `toBeDisabled()` sobre un elemento que ya no lo está. Son textos y roles que cambiaron sin que nadie actualizara el test.

### La trampa que no da error: MSW en modo aviso

[`src/test/setup.ts`](../frontend/src/test/setup.ts) arranca el servidor así:

```ts
server.listen({ onUnhandledRequest: 'warn' });
```

Una petición sin manejador **no rompe el test**: imprime un aviso y devuelve nada. Un test puede pasar entero sin haber probado absolutamente nada, y el aviso se pierde entre las 118 líneas de rojo preexistente. El comentario del propio fichero explica por qué está así —`'error'` rompería los tests unitarios que no hacen llamadas—, pero la consecuencia hay que conocerla.

*Cómo se escribe bien:* declarar los manejadores explícitamente para las rutas que el componente llama, o —lo que hace la mayoría de los tests de servicio de este repositorio— mockear el módulo del servicio con `vi.mock` y afirmar sobre `toHaveBeenCalledWith`, que es una comprobación que no puede pasar por accidente.

### `tsc --noEmit` no es una puerta

Devuelve decenas de errores preexistentes en los ficheros de plantilla de Metronic: `lucide-react` sin exportar `ShieldUser`, `VectorSquare` o `PanelTopBottomDashed`, módulos ausentes (`@/components/image-input`, `embla-carousel-react`), y tipos rotos en `chart.tsx` y `data-grid-table.tsx`. Filtra su salida a tus propios ficheros antes de sacar conclusiones. **La puerta real es `npm run build`**, que sí pasa en verde.

---

## 🔗 Recursos Externos

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Testing Library Cheatsheet](https://testing-library.com/docs/react-testing-library/cheatsheet/)
- [MSW Documentation](https://mswjs.io/docs/)
- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Testing Library - Which Query](https://testing-library.com/docs/queries/about#priority)
- [Kent C. Dodds - Testing JavaScript](https://testingjavascript.com/)

---

## 🎯 Conclusión

Esta combinación de herramientas ofrece:

- ✅ **Velocidad**: Vitest aprovecha Vite para tests ultra-rápidos
- ✅ **Confiabilidad**: Tests basados en comportamiento del usuario real
- ✅ **Multi-navegador**: Playwright testea en Chromium, Firefox y WebKit
- ✅ **Integración**: Compatible con GitHub Actions y free-tier
- ✅ **DX**: Excelente experiencia de desarrollo con hot reload y UI interactiva
- ✅ **Accesibilidad**: Testing Library promueve queries accesibles por defecto
