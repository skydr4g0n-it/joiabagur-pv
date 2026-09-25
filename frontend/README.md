# JoiaBagur PV - Frontend

Sistema de Gestión de Puntos de Venta para Joyería - Frontend Application

## Tech Stack

- **React 19** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **Radix UI** for accessible components
- **React Router v7** for routing
- **React Hook Form + Zod** for forms

## Getting Started

### Prerequisites

- Node.js 20+
- npm 10+

### Installation

```bash
cd frontend
npm install --legacy-peer-deps
```

### Development

```bash
npm run dev
```

The app will be available at [http://localhost:3000](http://localhost:3000)

### Build

```bash
npm run build
```

## Venta asistida y ficha de venta

Dos pantallas consumen la capa de IA, y las dos siguen la misma regla: **no se enseña nada que el
sistema no haya afirmado**. El frontend no reordena resultados, no recalcula precio ni existencias, no
añade avisos y no traduce un código que no conoce inventándose una etiqueta.

| Ruta | Pantalla | Qué consume |
|---|---|---|
| `/sales/new/assisted` | Panel de búsqueda asistida (C16), con **dos rutas** desde C40 | `POST /api/ai/search` · `POST /api/ai/search/assisted` · `GET /api/ai/search/availability` |
| `/sales/new/assist/:productId` | **Ficha de venta** (C36) | `POST /api/ai/products/{id}/sales-assist` y `GET /api/ai/products/{id}/substitutes` |

### Las dos rutas del panel (C40)

El mismo panel sirve **una búsqueda rápida** y **una respuesta asistida**, y un toggle elige. El
toggle **no recuerda** la elección y por defecto vale la semántica: la asistida cuesta una llamada
generativa, y un panel que recordara la cara acabaría gastándola sin que nadie la pidiera.

**La disponibilidad se lee antes de buscar.** `aiAvailable` viaja *dentro* de una respuesta, así que
hasta C40 la única forma de saber que una vía estaba apagada era usarla — y así es como el panel
sirvió por su ruta degradada durante todo el proyecto sin que nadie lo notara. `GET
/api/ai/search/availability` no cuesta cuota ni llama al servicio de IA, y alimenta una insignia de
cuatro estados y la opción deshabilitada del toggle, con su motivo al lado.

**La respuesta asistida puede llegar de dieciséis maneras** y las dieciséis se distinguen en
pantalla. No es una lista de mensajes: es una **unión discriminada** resuelta en
[`lib/free-query-states.ts`](src/lib/free-query-states.ts), porque los estados son combinaciones de
campos y una pantalla que ramificara campo a campo acertaría cada rama y fallaría las
combinaciones — que es exactamente cómo este panel llegó a tener cinco ramas de vacío, tres de
ellas capaces de pintar una respuesta correcta como un fallo. La tabla con la medición detrás de
cada estado está en
[`c40-m1-panel-states.md`](../Documentos/Proyecto%20Final%20AIEng/informes/c40-m1-panel-states.md).

Tres decisiones de copia que no son obvias:

- **«Sin resultados» no es `groups.length === 0`.** En la ruta de conocimiento el servicio responde
  desde el corpus y devuelve cero piezas a propósito; anunciar un vacío ahí escribiría un fallo
  justo encima de una respuesta correcta.
- **Los dos rechazos llevan textos distintos.** «No es una pregunta de joyería» y «no trabajamos ese
  tipo de pieza» son dos cosas distintas que decirle a un cliente, y el servicio se molesta en
  emitir dos códigos: colapsarlos aquí tiraría esa distinción en el último paso.
- **El estado sin ruta no siempre invita a reformular.** Con `intent=in_domain` el clasificador se
  contradijo y pedir otra redacción es justo; con `unclassified` no llegó a correr, y pedírselo al
  operario sería culparle de una configuración.

### La ficha de venta (`/sales/new/assist/:productId`)

Anclada a **una pieza y un punto de venta**, con carga perezosa. El punto de venta llega por **estado
de navegación**; abierta en frío ofrece el mismo selector por rol que el panel y **no emite ninguna
petición hasta que hay uno elegido**.

**Tres entradas**, todas con acción explícita:

| Origen | Acción | Estado que viaja |
|---|---|---|
| `components/sales/assisted-search-result-row.tsx` | «Ver ficha de venta», acción **secundaria** de la fila | `{ pointOfSaleId }` del panel |
| `pages/sales/new.tsx` | Botón junto al producto seleccionado | `{ pointOfSaleId }` del formulario |
| `pages/sales/scan.tsx` | Tras resolver el código | — *(esta página no tiene punto de venta; la ficha cae en su selector)* |

La salida es el traspaso que ya existía: `navigate(ROUTES.SALES.NEW, { state: { productId } })`, con el
identificador del **miembro que el operario eligió**.

**Cuatro reglas que es fácil romper sin querer**, y que tienen test:

1. **Una petición de asistencia por visita**, emitida al entrar. Navegar a la ficha *es* el acto
   explícito. El presupuesto es de **10 peticiones por minuto y usuario** y la respuesta **no se puede
   cachear**, así que re-renderizar, que llegue la respuesta o que algo falle no pueden producir otra.
2. **Ningún reintento automático.** El reintento lo pide el operario con un botón.
3. **La pregunta del cliente es una segunda petición** y viaja **en el cuerpo**, nunca en la dirección
   de la página ni en el estado del enrutador, que acaban en el historial del navegador. Máximo **500
   caracteres**, comprobados antes de enviar.
4. **Los sustitutos se disparan por `hasStock` del miembro anclado**, nunca por `pitchStatus`, y **no
   se piden** si la IA no estaba disponible para esa ficha.

### La tabla de copia (`src/lib/assist-copy.ts`)

El backend envía **códigos**; el castellano que lee una persona se escribe aquí. Módulo propio, con
funciones exportadas y **probadas directamente**, siguiendo el patrón de `originLabel` de la fila de
resultados — no literales repartidos por los componentes.

Cubre los **cinco códigos de aviso alcanzables**, los **cinco mensajes** de los seis estados del
argumentario, los **cuatro desenlaces** de sustitutos, el alcance de las citas y las **cinco preguntas
sugeridas** del corpus.

Tres cosas que parecen erratas y no lo son:

- **Dos códigos del vocabulario no tienen fila**: `query_out_of_domain` y `query_not_in_catalogue` los
  emite sólo el clasificador de intención, que corre en un modo que estas rutas no usan. Caen en la
  **etiqueta neutra**, y hay un test que lo comprueba en vez de copia muerta sobre caminos imposibles.
- **`size_label_missing` no entra en el bloque de avisos**: se pinta como atributo junto al SKU. Salta
  en el 58,3 % de las fichas y describe el enriquecimiento del catálogo, no la pieza. **Se pinta
  siempre**: no se suprime nada que el backend haya emitido.
- **`ai_unavailable` y `not_generated` no comparten mensaje**, aunque suenen parecido: en el primero la
  familia y los materiales vienen del catálogo transaccional y no hay citas; en el segundo vienen del
  índice. Fundirlos haría que la pantalla mintiera sobre la procedencia de lo que enseña.

## Testing

### Unit & Component Tests (Vitest + React Testing Library)

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui
```

### E2E Tests (Playwright)

```bash
# Install browsers (first time only)
npx playwright install

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI mode
npm run test:e2e:ui

# Run E2E tests in headed mode
npm run test:e2e:headed
```

### Test Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── ui/
│   │       ├── button.tsx
│   │       └── button.test.tsx    # Colocated test
│   ├── hooks/
│   │   ├── use-copy-to-clipboard.ts
│   │   └── use-copy-to-clipboard.test.ts
│   ├── lib/
│   │   ├── utils.ts
│   │   └── utils.test.ts
│   └── test/
│       ├── setup.ts               # Global test setup
│       ├── mocks/
│       │   ├── handlers.ts        # MSW request handlers
│       │   └── server.ts          # MSW server config
│       └── utils/
│           ├── render.tsx         # Custom render with providers
│           └── test-data.ts       # Test data factories
├── e2e/
│   ├── app.spec.ts                # E2E tests
│   └── fixtures/
│       └── test-user.json
├── playwright.config.ts
└── vite.config.ts                 # Vitest config included
```

### Test Conventions

- **Naming**: `should [behavior] when [condition]`
- **Structure**: AAA (Arrange, Act, Assert)
- **Queries**: Prefer accessible queries (`getByRole`, `getByLabelText`)
- **Coverage Target**: 70%

### Example Test

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/utils';
import userEvent from '@testing-library/user-event';
import { Button } from './button';

describe('Button', () => {
  it('should call onClick when clicked', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    
    render(<Button onClick={handleClick}>Click me</Button>);
    
    await user.click(screen.getByRole('button'));
    
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

## Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |
| `npm run test` | Run unit/component tests |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage |
| `npm run test:ui` | Run tests with Vitest UI |
| `npm run test:e2e` | Run E2E tests |
| `npm run test:e2e:ui` | Run E2E tests with Playwright UI |
| `npm run test:e2e:headed` | Run E2E tests in headed browser |

## License

Private - JoiaBagur
