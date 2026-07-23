## ADDED Requirements

### Requirement: Barcode/QR Code Camera Scanning

The system SHALL provide a camera-based barcode and QR code scanner in the sales flow that decodes codes client-side, extracts the SKU from the scanned value, and looks up the associated product for sale registration. This replaces the previous AI image recognition entry method.

#### Scenario: Scan QR code successfully

- **WHEN** operator opens the barcode scanning page (replacing the image recognition sales page)
- **AND** points the device camera at a QR code
- **AND** the decoded value matches an existing product SKU
- **AND** the product has an active Inventory record at the operator's assigned POS
- **THEN** the product is automatically selected in the sales form
- **AND** the operator proceeds to quantity and payment method entry
- **AND** a success toast "Producto seleccionado: [Name]" is displayed

#### Scenario: Scan barcode successfully

- **WHEN** operator points the device camera at a Code128 barcode (encoding a product SKU)
- **AND** the decoded value matches an existing product SKU
- **AND** the product is accessible (admin: all, operator: assigned POS only)
- **THEN** the product is auto-selected in the sales form
- **AND** flow continues to quantity/payment entry

#### Scenario: Scanned SKU does not match any product

- **WHEN** the camera decodes a QR or barcode value
- **AND** no product has that SKU value
- **THEN** an error toast is displayed: "Producto no encontrado: [SKU]"
- **AND** the scanner continues running for the next scan attempt
- **AND** the operator can switch to manual entry at any time

#### Scenario: Scanned product not assigned to operator's POS

- **WHEN** an operator scans a code matching a product SKU
- **AND** that product has no active Inventory record at the operator's assigned POS
- **THEN** an error toast is displayed: "Producto no asignado a este punto de venta"
- **AND** the scanner continues running
- **AND** the operator can switch to manual entry

#### Scenario: Camera permission denied

- **WHEN** operator opens the scanning page
- **AND** the device/browser denies camera access
- **THEN** an error message is displayed: "Permiso de cámara denegado"
- **AND** a button to navigate to manual product entry is shown
- **AND** the scanning page offers fallback to manual entry

#### Scenario: Scanning view with flash/torch toggle

- **WHEN** operator opens the scanning page
- **AND** the device has a flash/torch capability
- **THEN** a flash toggle button is displayed
- **AND** operator can enable/disable the flash
- **AND** flash defaults to off

#### Scenario: Continuous decode mode

- **WHEN** the scanning view is active
- **THEN** the camera feed is continuously analyzed for barcodes/QR codes
- **AND** decoded values are shown as an overlay on the camera feed
- **AND** the viewport has a visible scan area indicator (e.g., corner brackets)
- **AND** decoding stops automatically once a valid product match is found

#### Scenario: Manual SKU entry fallback

- **WHEN** operator is in the scanning view
- **AND** scanning fails repeatedly or camera is unavailable
- **THEN** a manual SKU input field is available
- **AND** operator can type the SKU value and submit
- **AND** the same product lookup logic applies

#### Scenario: Image recognition page replaced

- **WHEN** operator navigates to the sales landing page
- **THEN** the "Reconocimiento de imagen" tile is NOT shown
- **AND** the "Escanear código" tile is shown as the primary camera-based entry method
- **AND** the image recognition page component and API endpoints remain intact in the codebase (not deleted)

### Requirement: SKU-Based Product Lookup

The system SHALL use the existing product search endpoint (`GET /api/products/search?query={sku}`) to look up products by scanned SKU, with role-based filtering.

#### Scenario: Lookup product by exact SKU as admin

- **WHEN** the scanning page calls GET /api/products/search?query={sku} with an exact SKU
- **AND** an authenticated administrator is logged in
- **AND** a product with that SKU exists
- **THEN** the system returns the product as the first/highlighted result
- **AND** includes Id, SKU, Name, Price, PrimaryPhotoUrl, and available stock

#### Scenario: Lookup product by exact SKU as operator

- **WHEN** the scanning page calls GET /api/products/search?query={sku} with an exact SKU
- **AND** an authenticated operator is logged in
- **AND** the product has active Inventory at the operator's assigned POS
- **THEN** the system returns the product with stock quantity at that POS

#### Scenario: Lookup by SKU — product not found

- **WHEN** the scanned SKU does not match any product
- **THEN** the search endpoint returns an empty array
- **AND** the scanning page shows "Producto no encontrado: [SKU]"

### Requirement: QR Code Label Generation

The system SHALL provide a mechanism for administrators to generate and download scannable QR code labels that encode each product's SKU.

#### Scenario: Generate single product QR label

- **WHEN** an authenticated administrator requests GET /api/products/{id}/qrcode
- **THEN** the system returns an SVG image containing a QR code encoding the product's SKU
- **AND** the QR code includes the product SKU and name as a caption below the code
- **AND** returns 200 OK with Content-Type: image/svg+xml

#### Scenario: Batch QR code label export

- **WHEN** an authenticated administrator requests GET /api/products/qrcodes/batch
- **AND** optionally filters by product IDs or collection
- **THEN** the system generates a downloadable PDF containing QR labels for all matching products
- **AND** each label shows the QR code, product SKU, and product name
- **AND** labels are laid out in a printable grid (e.g., 4x6 per page)

#### Scenario: Unauthorized label generation

- **WHEN** an operator or unauthenticated user requests label generation
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: QR and Barcode Display on Product Detail Page

The system SHALL display a generated QR code and Code128 barcode on the product detail/edit page, giving administrators a quick visual reference of the scannable codes for each product.

#### Scenario: Show QR code on product edit page

- **WHEN** an administrator navigates to the product edit page for a product with a valid SKU
- **THEN** a rendered QR code is displayed, encoding the product's SKU
- **AND** the QR code is displayed as a small SVG or PNG image (e.g., 150x150px)
- **AND** a "Descargar QR" button is available below the QR code for single-label download

#### Scenario: Show Code128 barcode on product edit page

- **WHEN** an administrator navigates to the product edit page
- **THEN** a Code128 barcode is displayed next to or below the QR code, encoding the same SKU
- **AND** the barcode is displayed as an SVG image
- **AND** the human-readable SKU text is shown below the barcode bars
- **AND** a "Descargar código de barras" button is available

#### Scenario: QR and barcode sections hidden for products with empty SKU

- **WHEN** a product has an empty or whitespace-only SKU
- **THEN** the QR code and barcode sections are not displayed
- **AND** a message "Genere un SKU para ver los códigos" is shown in their place

#### Scenario: QR and barcode visible to operators (read-only)

- **WHEN** an operator views the product edit page
- **THEN** the QR code and barcode sections are displayed (read-only, same as admin)
- **AND** the download buttons are also available
