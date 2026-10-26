# frontend Specification

## Purpose

Define the React + Metronic SPA shell, routing, layout, and shared UI patterns used across authenticated features.

## Requirements
### Requirement: Layout Configuration

The frontend SHALL use Metronic Layout 8 (sidebar navigation) as the primary application layout, providing consistent navigation structure across all authenticated pages.

#### Scenario: Default Layout Rendering
- **WHEN** user navigates to any authenticated route
- **THEN** Layout 8 renders with sidebar, header, and main content area
- **AND** sidebar displays project-specific navigation menu

#### Scenario: Responsive Behavior
- **WHEN** application is viewed on mobile device
- **THEN** sidebar collapses to hamburger menu
- **AND** navigation remains accessible via drawer

### Requirement: Project Routing Structure

The frontend SHALL implement a modular routing structure organized by business domain (epic), with lazy loading for optimal bundle size.

#### Scenario: Route Organization
- **WHEN** navigating to a module
- **THEN** URL reflects the module path (e.g., `/products`, `/inventory`, `/sales`)
- **AND** appropriate page component is rendered within Layout 8

#### Scenario: Default Route
- **WHEN** user navigates to root path `/`
- **THEN** user is redirected to `/dashboard`

#### Scenario: Lazy Loading
- **WHEN** page component is requested
- **THEN** component is loaded on demand
- **AND** initial bundle size remains under 500KB

#### Scenario: Dashboard role bifurcation
- **WHEN** authenticated user navigates to `/dashboard`
- **THEN** the dashboard page component determines user role from auth context
- **AND** renders AdminDashboard for Administrator role
- **AND** renders OperatorDashboard for Operator role

### Requirement: Sidebar Navigation Menu

The frontend SHALL display a role-based sidebar menu with icons and clear labels in Spanish, showing different navigation options based on user role.

#### Scenario: Administrator Menu Structure
- **WHEN** sidebar is visible for an Administrator user
- **THEN** menu displays: Dashboard, Inventario, Ventas, Devoluciones, Reportes, Configuración
- **AND** Configuración contains submenu: Productos, Métodos de Pago, Usuarios, Puntos de Venta
- **AND** each item has an appropriate icon

#### Scenario: Operator Menu Structure
- **WHEN** sidebar is visible for an Operator user
- **THEN** menu displays: Dashboard, Ventas, Devoluciones, Inventario
- **AND** no access to Configuración, Reportes, or administrative functions
- **AND** each item has an appropriate icon

#### Scenario: Active State
- **WHEN** user is on a specific module page
- **THEN** corresponding sidebar menu item is visually highlighted

#### Scenario: Menu Rendering Based on Auth Context
- **WHEN** user role changes or user logs in
- **THEN** sidebar menu re-renders with appropriate menu for the role

### Requirement: API Client Configuration

The frontend SHALL provide a centralized HTTP client service configured with the backend API base URL from environment variables.

#### Scenario: Environment-based Configuration
- **WHEN** application starts
- **THEN** API client reads base URL from `VITE_API_BASE_URL`
- **AND** all API requests use this base URL

#### Scenario: Request Interceptor Support
- **WHEN** API request is made
- **THEN** request passes through interceptor chain
- **AND** Authorization header can be added (when auth is implemented)

#### Scenario: Error Handling
- **WHEN** API request fails
- **THEN** error is captured by response interceptor
- **AND** appropriate error handling can be applied

### Requirement: Type Definitions

The frontend SHALL provide TypeScript type definitions for common API response patterns and shared domain types.

#### Scenario: API Response Types
- **WHEN** API response is received
- **THEN** response can be typed with generic wrapper types
- **AND** TypeScript provides autocomplete and type checking

#### Scenario: Pagination Types
- **WHEN** paginated data is requested
- **THEN** response includes typed pagination metadata
- **AND** page size is limited to 50 items maximum per project constraints

### Requirement: Environment Configuration

The frontend SHALL support environment-based configuration via `.env` files compatible with Vite.

#### Scenario: Development Environment
- **WHEN** running in development mode
- **THEN** `.env.development` values are loaded
- **AND** API points to local backend

#### Scenario: Environment Variable Prefix
- **WHEN** accessing environment variables
- **THEN** only variables prefixed with `VITE_` are exposed to client code
- **AND** sensitive values are not leaked

### Requirement: Folder Organization

The frontend SHALL maintain a consistent folder structure separating concerns: pages by module, shared services, reusable types, and context providers.

#### Scenario: Service Location
- **WHEN** creating a new API service
- **THEN** service is placed in `services/` directory
- **AND** follows naming convention `[module].service.ts`

#### Scenario: Type Location
- **WHEN** creating shared types
- **THEN** types are placed in `types/` directory
- **AND** domain-specific types are in `[domain].types.ts`

#### Scenario: Page Location
- **WHEN** creating module pages
- **THEN** pages are placed in `pages/[module]/` directory
- **AND** main page is named `page.tsx` or `index.tsx`

### Requirement: Currency and Localization

The frontend SHALL display all monetary values using Euro (EUR) currency format with Spanish (Spain) locale formatting conventions.

#### Scenario: Price Display Format
- **WHEN** displaying product prices, sale totals, or any monetary value
- **THEN** the currency symbol € (Euro) is shown
- **AND** numbers are formatted using Spanish locale (es-ES) with comma as decimal separator
- **AND** minimum 2 decimal places are displayed

#### Scenario: Currency Formatting with Intl API
- **WHEN** using Intl.NumberFormat for currency display
- **THEN** locale is set to 'es-ES'
- **AND** currency is set to 'EUR'
- **AND** style is set to 'currency'

#### Scenario: Simple Price Display
- **WHEN** displaying prices without full Intl formatting
- **THEN** the € symbol precedes the numeric value
- **AND** two decimal places are shown (e.g., €299.99)

### Requirement: Operator Dashboard Layout

The frontend SHALL provide an OperatorLayout wrapper for the operator dashboard that hides the Metronic sidebar and displays a sticky bottom action bar, optimizing screen real estate for mobile/tablet POS use.

#### Scenario: Sidebar hidden on operator dashboard
- **WHEN** authenticated operator views the dashboard
- **THEN** the Layout 8 sidebar is hidden or collapsed
- **AND** the full viewport width is available for dashboard content

#### Scenario: Sidebar visible on other operator pages
- **WHEN** authenticated operator navigates away from the dashboard
- **THEN** the Layout 8 sidebar returns to its normal behavior
- **AND** standard navigation is available

#### Scenario: Admin layout unaffected
- **WHEN** authenticated administrator views the dashboard
- **THEN** the Layout 8 sidebar remains visible in its standard configuration
- **AND** no OperatorLayout wrapper is applied

### Requirement: Dashboard Chart Components

The frontend SHALL use Recharts for rendering line, bar, and donut chart components on the dashboard, keeping bundle impact minimal through lazy loading.

#### Scenario: Chart library loaded on demand
- **WHEN** user navigates to the dashboard
- **THEN** Recharts components are loaded as part of the lazy-loaded dashboard page
- **AND** chart library does not increase the initial bundle size

#### Scenario: Charts display with Euro formatting
- **WHEN** charts display monetary values on axes or tooltips
- **THEN** values are formatted using Intl.NumberFormat with locale 'es-ES' and currency 'EUR'

### Requirement: Persistent Sales Cart State
The frontend SHALL provide a sales cart state container that persists cart lines in browser storage and restores them across page reloads.

#### Scenario: Cart state survives reload
- **WHEN** the operator adds one or more lines to the sales cart
- **AND** reloads the browser tab
- **THEN** the cart state is restored from persisted storage
- **AND** line metadata needed for UI rendering remains available

### Requirement: Cart Expiration Policy
The frontend SHALL apply a cart time-to-live policy of 10 hours of inactivity so stale carts are automatically invalidated.

#### Scenario: Expire stale cart on next access
- **WHEN** cart data exceeds 10 hours since last cart activity
- **THEN** frontend clears stale cart data before checkout interactions
- **AND** informs the user that the previous cart expired

### Requirement: Cart Composition Constraints
The frontend SHALL enforce single point-of-sale and single payment-method composition rules while adding new lines to cart.

#### Scenario: Reject line with different point of sale
- **WHEN** cart already contains lines from one point of sale
- **AND** operator attempts to add a line with a different point of sale
- **THEN** frontend blocks the addition
- **AND** displays a validation message explaining the mismatch

#### Scenario: Reject line with different payment method when fixed
- **WHEN** cart already has an established payment method context
- **AND** operator attempts to add a line with a different payment method
- **THEN** frontend blocks the addition
- **AND** keeps existing cart unchanged

### Requirement: Sales Cart Page and Checkout Confirmation
The frontend SHALL provide route `/sales/cart` with line listing, line removal, totals, payment method selection, and a confirmation dialog before bulk submission.

#### Scenario: Remove line from cart
- **WHEN** operator removes a line in `/sales/cart`
- **THEN** the line is deleted from cart state
- **AND** totals and badge count update immediately

#### Scenario: Confirm bulk checkout from cart
- **WHEN** operator opens checkout confirmation in `/sales/cart`
- **THEN** dialog shows line count, total amount, selected payment method, and global note input
- **AND** confirming sends a bulk request to the backend

### Requirement: Per-Line Stock Revalidation in Cart
The frontend SHALL revalidate stock for each cart line against the selected point of sale before allowing checkout.

#### Scenario: Stock insufficient for one or more lines
- **WHEN** revalidation detects `quantity > available stock` for any line
- **THEN** frontend marks affected lines as insufficient stock
- **AND** disables the checkout action
- **AND** communicates which lines must be removed before retrying

### Requirement: Sales Entry Points and Cart Visibility
The frontend SHALL expose cart access from sales entry pages and sales navigation, including a line-count badge.

#### Scenario: Add to cart from manual sales page
- **WHEN** operator completes valid form data in `/sales/new`
- **THEN** frontend provides action "Añadir al carrito"
- **AND** added line appears in cart count immediately

#### Scenario: View cart from image sales page
- **WHEN** the cart has at least one line
- **THEN** `/sales/new/image` shows action "Ver carrito"
- **AND** action navigates to `/sales/cart`

#### Scenario: Cart badge in sales layout
- **WHEN** user navigates inside `/sales/*`
- **THEN** sales layout/nav displays a cart badge with current line count
- **AND** clicking badge navigates to `/sales/cart`
