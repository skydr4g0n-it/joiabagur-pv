## 1. Backend: QR Code Label Generation

- [x] 1.1 Add `QRCoder` NuGet package to Infrastructure/Application layer
- [x] 1.2 Create `IQrCodeService` interface in Application layer with `GenerateSvg(sku)` method
- [x] 1.3 Implement `QrCodeService` using QRCoder to generate SVG from a product's SKU
- [x] 1.4 Add `GET /api/products/{id}/qrcode` endpoint returning SVG (Content-Type: image/svg+xml)
- [x] 1.5 Add `GET /api/products/qrcodes/batch` endpoint generating a printable PDF with QR labels for filtered product list
- [x] 1.6 Enforce admin-only authorization for QR generation endpoints

## 2. Backend: Tests

- [x] 2.1 Unit test: `QrCodeService.GenerateSvg_WithValidSku_ReturnsValidSvg`
- [x] 2.2 Unit test: `QrCodeService.GenerateSvg_WithEmptySku_ThrowsException`
- [x] 2.3 Integration test: `ProductsController.GetQrCode_AsAdmin_ReturnsSvg`
- [x] 2.4 Integration test: `ProductsController.GetQrCode_AsOperator_Returns403`
- [x] 2.5 Integration test: `ProductsController.GetQrCodeBatch_AsAdmin_ReturnsPdf`

## 3. Frontend: Dependencies

- [x] 3.1 Install `quagga2` and `jsQR` npm packages in frontend
- [x] 3.2 Verify bundle size impact (target: < 25KB gzipped combined)

## 4. Frontend: Barcode Scanner Service

- [x] 4.1 Create `barcode-scanning.service.ts` with `BarcodeScanningService` class
- [x] 4.2 Implement `startCamera(videoElement)` — request `getUserMedia` with environment-facing camera, wire to video element
- [x] 4.3 Implement `stopCamera()` — stop all tracks, clean up
- [x] 4.4 Implement `scanBarcode(canvasElement, videoElement)` — capture frame, run quagga2 decode
- [x] 4.5 Implement `scanQrCode(canvasElement, videoElement)` — capture frame, run jsQR decode
- [x] 4.6 Implement `continuousScan(videoElement, canvasElement, onDecode)` — requestAnimationFrame loop decoding at ~5fps
- [x] 4.7 Implement `toggleFlash()` — enable/disable video torch mode if available
- [x] 4.8 Implement device compatibility check (`navigator.mediaDevices?.getUserMedia`)

## 5. Frontend: Scanning Page (replaces new-image.tsx)

- [x] 5.1 Create new scanning page component at `pages/sales/scan.tsx` with fullscreen camera preview
- [x] 5.2 Add scan area overlay with corner brackets and instructions text
- [x] 5.3 Implement continuous decode loop with debounce (ignore duplicate decodes within 2s)
- [x] 5.4 Show loading state while camera initializes; show error if camera unavailable
- [x] 5.5 Add flash/torch toggle button
- [x] 5.6 Add manual SKU input field as fallback below the camera view
- [x] 5.7 On successful decode: call `GET /api/products/search?query={sku}`, validate exact match, auto-select product, navigate to sale form
- [x] 5.8 Handle scan errors (product not found, not assigned to POS) with toast notifications and option to retry
- [x] 5.9 Add close/back button to return to sales landing page

## 6. Frontend: Sales Landing Page — Replace Image Recognition Tile

- [x] 6.1 Remove the "Reconocimiento de imagen" tile/link from `pages/sales/index.tsx`
- [x] 6.2 Add "Escanear código" tile as the new primary camera-based entry method, linking to the new scan page
- [x] 6.3 Update `ROUTES` constant: add `/sales/new/scan` route, keep `/sales/new/image` route but remove it from navigation
- [x] 6.4 Do NOT delete `pages/sales/new-image.tsx` or its imports/services — leave them intact

## 7. Frontend: QR and Barcode Display on Product Edit Page

- [x] 7.1 Generate QR code SVG inline on the product edit page (client-side using `qrcode` lib or via `GET /api/products/{id}/qrcode` SVG embed)
- [x] 7.2 Add a QR code display section on the edit page showing the generated QR (150x150px) with a "Descargar QR" button
- [x] 7.3 Generate a Code128 barcode SVG inline client-side (use `JsBarcode` or similar lightweight lib) encoding the product's SKU
- [x] 7.4 Add a barcode display section on the edit page showing the Code128 barcode with human-readable SKU text and a "Descargar código de barras" button
- [x] 7.5 Hide both sections when the product has no SKU, showing placeholder text instead
- [x] 7.6 Ensure both sections are visible to operators (read-only, same as admin)

## 8. Frontend: Tests

- [x] 8.1 Test: `BarcodeScanningService.startCamera_startsVideoStream` (mock getUserMedia)
- [x] 8.2 Test: `BarcodeScanningService.stopCamera_stopsAllTracks`
- [x] 8.3 Test: scanning page renders loading state initially
- [x] 8.4 Test: scanning page shows manual SKU input fallback
- [x] 8.5 Test: sales landing page shows "Escanear código" and "Registro manual", not "Reconocimiento de imagen"
- [x] 8.6 Test: product edit page renders QR code for product with SKU
- [x] 8.7 Test: product edit page renders Code128 barcode for product with SKU
- [x] 8.8 Test: product edit page hides QR/barcode sections when SKU is empty

## 9. Documentation

- [x] 9.1 Update `Documentos/Guias/ventas-registro.md` — replace image recognition procedure with barcode/QR scanning procedure
