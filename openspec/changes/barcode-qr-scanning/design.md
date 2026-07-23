## Context

The current sales flow offers two product identification methods: manual SKU/name search and AI-powered image recognition via TensorFlow.js. In practice, image recognition is unreliable for jewelry (visually similar items, varying lighting) and requires frequent model retraining. Operators need a faster, more reliable way to identify products. Barcode/QR code scanning is the industry standard for retail POS.

The design replaces the image recognition entry in the sales UI with barcode/QR scanning, keeping the existing image recognition code intact but hidden. The QR code simply encodes each product's existing SKU — no new database fields needed.

## Goals / Non-Goals

**Goals:**
- Replace the image recognition sales page with a camera-based barcode/QR scanner that decodes SKUs and looks up products
- Generate scannable QR codes server-side from each product's SKU for printing/labeling
- Support Code128 barcode generation from SKU (for label printers that prefer 1D codes)
- Keep all existing image recognition code (backend + frontend) intact but hide the UI entry point
- No database schema changes

**Non-Goals:**
- Not adding any new database fields or migrations
- Not deleting or modifying existing image recognition code
- Not adding physical label printer integration (labels are downloaded as PDF/SVG and printed externally)
- Not implementing server-side barcode decoding (all decoding is client-side)
- Not adding a dedicated barcode scanner hardware integration (uses device camera only)
- Not modifying the Product entity or its CRUD in any way

## Decisions

### Decision 1: SKU as the barcode/QR identifier vs. new Barcode field
**Choice**: Use the existing SKU as the value encoded in QR codes and barcodes. No new database field.
**Rationale**: SKUs are already unique per product and are already the primary lookup key. Encoding the SKU in a QR code means any external system can scan the code and get the SKU directly — no proprietary format. Generating on-the-fly avoids data duplication, migration overhead, and sync issues.
**Alternative considered**: New Barcode field (from original proposal) — rejected per user feedback. Unnecessary complexity.

### Decision 2: QR and Code128 from SKU
**Choice**: QR codes and Code128 barcodes both encode the SKU string directly. QR for camera scanning (mobile-first), Code128 for label printers.
**Rationale**: QR codes are easy to scan with phone cameras and can encode alphanumeric SKUs. Code128 is the most common 1D barcode format for retail and supports alphanumeric data. Providing both gives flexibility for different workflows.
**Implementation**: Server-side QRCoder generates QR SVG. Client-side, the scanned QR/barcode value IS the SKU — product lookup uses the existing search endpoint or a dedicated SKU lookup.

### Decision 3: Client-side barcode/QR decoding
**Choice**: Decode entirely client-side using the device camera via `quagga2` (barcodes) and `jsQR` (QR codes).
**Rationale**: Same as original — no round-trip, works offline for decoding, lightweight (~25KB combined).

### Decision 4: QR code generation
**Choice**: Server-side SVG generation via QRCoder, encoding the SKU.
**Rationale**: Same as original. The QR code payload is simply `Product.SKU`. Batch PDF export for label printing.

### Decision 5: Sales page — replace image recognition
**Choice**: The sales landing page shows two options: "Escanear código" and "Registro manual". The image recognition tile is removed. The `new-image.tsx` component and all its supporting code (TF.js services, API endpoints) remain in the repository but are no longer routed from the UI.
**Rationale**: Reduces operator confusion (only one camera-based method). Code preservation avoids regressions if needed later.
**Implementation**: Remove the `Link` to `/sales/new/image` from the sales landing page. The route and page component stay importable but unreachable from navigation. No backend changes to image recognition controllers or services.

### Decision 6: Product lookup from scanned SKU
**Choice**: Use the existing `GET /api/products/search?query={sku}` endpoint for scanning lookup.
**Rationale**: The search endpoint already supports exact SKU matching with role-based filtering. A new endpoint is unnecessary — when the scanned value is an exact SKU, it matches first/highlighted. This keeps the backend surface minimal.
**Alternative**: A dedicated `GET /api/products/sku/{sku}` endpoint — viable but adds unnecessary API surface since search works. Will use search for simplicity, add dedicated endpoint only if performance requires it.

## Risks / Trade-offs

- **[SKU format limitations]** SKUs with special characters (spaces, symbols) may not scan reliably as Code128. The QR code handles any character. Mitigation: prefer QR for camera scanning; advise admin to keep SKUs alphanumeric for barcode compatibility.
- **[SKU length]** Very long SKUs produce denser QR codes that are harder to scan. Skus under 20 chars scan easily. Not a concern given ~500 products.
- **[Camera permission]** Same as original — manual entry is always a fallback.
- **[Offline scanning]** Decoding works offline, but product lookup needs the API. Error message guides to manual entry.
- **[Code not deleted]** Image recognition code stays in the codebase but is dead code from the user's perspective. This is intentional for rollback.
