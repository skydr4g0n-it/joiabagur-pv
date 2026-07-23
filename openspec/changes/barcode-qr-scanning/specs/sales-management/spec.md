## MODIFIED Requirements

### Requirement: Sales Registration with Entry Methods

The system SHALL allow operators to register sales using two methods: barcode/QR code scanning (replacing image recognition) or manual product selection (with optional photo). The image recognition entry point is removed from the UI, but its backend controllers and frontend components remain intact in the codebase. All methods validate stock availability, payment method assignment, operator authorization, and point-of-sale price policy before creating sale records.

#### Scenario: Create sale with barcode/QR scanning successfully

- **WHEN** authenticated operator scans a QR code or barcode
- **AND** the decoded value matches an existing product SKU
- **AND** the product has active Inventory at the operator's POS
- **AND** operator enters quantity (>= 1)
- **AND** selects payment method assigned to point of sale
- **AND** product has sufficient stock at point of sale
- **THEN** system creates Sale record using effective sale price rules (official Product.Price by default, optional override only if POS allows manual price edit)
- **AND** SalePhoto is null (no photo attached unless operator explicitly adds one via manual flow)
- **AND** creates InventoryMovement record with type "Sale" (via inventory-management integration)
- **AND** updates Inventory.Quantity atomically in same transaction
- **AND** returns success with sale ID and low stock warning if applicable

#### Scenario: Create sale with image recognition (deprecated — code retained)

- **WHEN** authenticated operator navigates to the sales landing page
- **THEN** the "Reconocimiento de imagen" tile is NOT displayed
- **AND** the `GET /api/image-recognition/*` endpoints remain functional
- **AND** the `new-image.tsx` React component remains in the codebase
- **AND** the image recognition route (`/sales/new/image`) still resolves if accessed directly

#### Scenario: Create manual sale without photo

- **WHEN** authenticated operator searches and selects product by SKU or name
- **AND** enters quantity (>= 1)
- **AND** selects payment method assigned to point of sale
- **AND** product has sufficient stock at point of sale
- **THEN** system creates Sale record using effective sale price rules
- **AND** SalePhoto is null (no photo attached)
- **AND** creates InventoryMovement and updates stock atomically
- **AND** returns success with sale ID

#### Scenario: Create manual sale with optional photo

- **WHEN** authenticated operator manually selects product
- **AND** optionally attaches photo (e.g., for documentation purposes)
- **AND** enters quantity and selects payment method
- **AND** product has sufficient stock
- **THEN** system creates Sale using effective sale price rules
- **AND** creates SalePhoto with compressed photo
- **AND** creates InventoryMovement and updates stock atomically

#### Scenario: Sales landing page with two entry methods

- **WHEN** authenticated operator navigates to the sales landing page
- **THEN** two entry options are displayed: "Escanear código" (barcode/QR) and "Registro manual"
- **AND** "Escanear código" is displayed as the first/primary option
- **AND** "Reconocimiento de imagen" is no longer shown

#### Scenario: Switch from scanning to manual entry

- **WHEN** operator is in the barcode scanning view
- **AND** the camera is unable to decode a readable code after multiple attempts
- **THEN** a "Entrada manual" button is visible
- **AND** clicking it navigates to the manual product search
