## Why

The current AI image recognition for product identification at the point of sale is unreliable in practice — jewelry items are visually similar, lighting conditions vary, and the TensorFlow.js model requires frequent retraining with limited accuracy. This creates frustration for operators and slows down sales. A barcode/QR code approach is simpler, faster, and near-100% reliable: each product's SKU is encoded into a scannable QR code (or barcode) that an operator reads with the device camera to instantly identify and select the product in the sales screen.

## What Changes

- **No database changes**: QR codes and barcodes are generated on-the-fly from each product's existing SKU. No new fields, no migration.
- **Replace** the image recognition sales page (`/sales/new/image`) with a barcode/QR scanning page. The existing image recognition code stays intact in the codebase but is hidden from the UI.
- Generate scannable QR codes server-side from the SKU (on-demand for printing/labeling). The QR code simply encodes the SKU value.
- Implement client-side barcode/QR decoding via the device camera using a lightweight JavaScript library (e.g., `quagga2` for barcodes, `jsQR` for QR codes).
- Support both flows: (1) scan QR code → decode SKU → look up product → proceed to sale, (2) scan barcode (Code128 encoding the SKU) → same flow.
- Since the QR code encodes the SKU, any external application can also generate and scan these codes without integration.
- Show a generated QR code and Code128 barcode on the product detail/edit page for quick visual reference.
- Keep existing image recognition backend/frontend code untouched (hidden, not deleted).

## Capabilities

### New Capabilities
- `barcode-scanning`: Frontend camera-based barcode and QR code decoding that reads the SKU from scanned codes and looks up the product in the sales screen, replaceing AI image recognition as the primary product identification method

### Modified Capabilities
- `sales-management`: Replace image recognition entry method with barcode/QR scanning on the sales landing page
- `image-recognition`: Keep all code intact; hide the UI entry point (deprecated but not removed)

## Impact

- **Backend**: No new database fields. Existing SKU-based product lookup (`GET /api/products/search`) already supports this. New endpoint for QR code label generation from SKU (`GET /api/products/{id}/qrcode`). Batch QR label export for printing.
- **Frontend**: Replace the image recognition scanning page (`new-image.tsx`) with a new barcode/QR scanning page. Library addition: `quagga2` + `jsQR` (~25KB gzipped). The image recognition page component and service remain in the codebase but the route is removed from the sales landing page. Show generated QR code and Code128 barcode on the product detail/edit page for quick reference.
- **Dependencies**: Add `quagga2` + `jsQR` to frontend `package.json`. Server-side QR code generation: `QRCoder` NuGet package.
- **Data**: No migration. No data loss. No new columns.
- **Documentation**: Update `Documentos/Guias/ventas-registro.md` — replace image recognition procedure with scanning procedure.
