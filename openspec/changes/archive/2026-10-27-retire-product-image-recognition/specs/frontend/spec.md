## ADDED Requirements

### Requirement: No product-photo recognition navigation
The frontend SHALL NOT list "Modelo de IA" in the sidebar and SHALL NOT register routes for `/admin/ai-model` or `/sales/new/image`.

#### Scenario: Administrator menu omits the model entry
- **GIVEN** an authenticated administrator
- **WHEN** the sidebar is rendered
- **THEN** no menu item is labeled "Modelo de IA"
- **AND** no menu item links to `/admin/ai-model`

#### Scenario: Retired paths are not routed
- **GIVEN** the application router
- **WHEN** a user navigates to `/admin/ai-model` or `/sales/new/image`
- **THEN** no recognition page component is loaded
- **AND** the existing catch-all navigates to `/dashboard`

## MODIFIED Requirements

### Requirement: Sales Entry Points and Cart Visibility
The frontend SHALL expose cart access from the manual sales page and sales navigation, including a line-count badge. The frontend SHALL NOT expose an image-recognition sales page.

#### Scenario: Add to cart from manual sales page
- **GIVEN** an operator on `/sales/new`
- **WHEN** the operator completes valid form data
- **THEN** the frontend provides the action "Añadir al carrito"
- **AND** the added line appears in the cart count immediately

#### Scenario: Cart badge in sales layout
- **GIVEN** a user navigating inside `/sales/*`
- **WHEN** the sales layout is shown
- **THEN** the sales layout or nav displays a cart badge with the current line count
- **AND** clicking the badge navigates to `/sales/cart`

#### Scenario: Image sales page is not a cart entry point
- **GIVEN** the cart has at least one line
- **WHEN** the user opens `/sales/new/image`
- **THEN** the application does not render a recognition page with "Ver carrito"
- **AND** the existing catch-all navigates to `/dashboard`
