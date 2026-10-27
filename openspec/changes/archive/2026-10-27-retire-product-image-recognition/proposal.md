## Why

Product-photo image recognition is no longer used, but the admin still sees model-health warnings and the UI still exposes training, inference, and the AI-model dashboard. Those surfaces should disappear. The backend implementation stays in the repository, marked deprecated, while its HTTP API reports that the capability has been withdrawn.

## What Changes

- Remove every frontend warning, page, route, menu entry, service, and test that exists only for product-photo recognition (model-health toast, `/admin/ai-model`, `/sales/new/image`, TensorFlow.js training and inference). Do not add dedicated redirects. The existing unmatched-route rule already sends unknown paths to `/dashboard`.
- Keep product photo upload, primary photo, and deletion as catalog management. Stop generating embeddings in the browser on upload, and remove copy that presents those photos as recognition references.
- **BREAKING**: Every endpoint on `ImageRecognitionController` (model metadata, health, versions, files, retrain, training dataset, class labels, and embeddings) keeps its implementation in source but responds that the capability is withdrawn (HTTP 410). Do not delete controllers, services, DTOs, tests scaffolding, or DI registration; mark them deprecated and point the live responses at the withdrawal.
- Do not add migrations and do not drop tables or columns (`ModelMetadata`, `ProductPhotoEmbedding`, `SalePhoto`, or related storage). Existing rows stay.
- Update current product documentation and active OpenSpec requirements so recognition is no longer an available sales or admin capability. On archived OpenSpec changes and master-course notes that describe this product feature, add a short banner that the feature was withdrawn and leave the historical body unchanged.
- Sales registration remains manual (cart and checkout unchanged). Historical sale photos, if already shown in sales history, stay readable. There is no new photo-capture flow for recognition.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `image-recognition`: Client inference, training, health alerts, and the admin model dashboard are removed. The API reports the capability as withdrawn instead of serving models or metrics.
- `embedding-management`: The browser no longer generates or deletes embeddings on photo upload. Embedding endpoints report withdrawal. Stored embedding rows remain.
- `embedding-similarity-inference`: In-browser cosine-similarity suggestions are removed with the recognition UI.
- `embedding-testing`: Frontend embedding and similarity tests are removed. Backend embedding tests expect the withdrawn API response.
- `sales-management`: Operators register sales only through manual selection. The AI-assisted entry method and its attached capture flow are removed. Manual stock, payment, and price rules stay.
- `frontend`: Sidebar no longer includes "Modelo de IA". `/sales/new/image` is not a sales entry point. Cart access remains on the manual sales flow.
- `product-management`: Product photo management stays. Upload copy and client behavior no longer train or embed for recognition.
- `backend`: ML model storage and distribution is no longer a live serving capability. Types and endpoints are deprecated and the HTTP surface reports withdrawal. Schema and stored files stay.

## Impact

- Frontend: `App.tsx`, `model-health-alert`, `pages/admin/ai-model`, `pages/sales/new-image`, `image-recognition.service`, `model-training.service`, sales image-recognition client in `sales.service`, routes, `menu.config`, product photo upload, related unit tests, and the `@tensorflow/tfjs` dependency. Metronic layout-38 demo selectors (GPT/Claude/Gemini) are unrelated template UI and stay.
- Backend: `ImageRecognitionController` and the application services it calls (`ImageRecognitionService`, `ModelHealthService`, embedding upload/query). Integration tests that call those routes. Sales, product photo, inventory, and gift-card APIs stay behavioral as they are today.
- Docs: `README.md`, `Documentos/epicas.md`, historias (EP4 and the image-sale story), `Documentos/Guias/admin-modelo-ia.md`, `ventas-registro.md`, `arquitectura.md`, `modelo-c4.md`, `modelo-de-datos.md`. Archived OpenSpec changes and master notes get a banner only.
- Specs listed above. No new user stories. EP4 and HU-EP4-001 / HU-EP3-001 are marked withdrawn in current docs, not replaced with a new epic.

## Out of scope

- Deleting backend recognition code, domain types, migrations, database tables, or stored model files.
- Removing product photo catalog management or changing photo storage (local/S3).
- Adding a dedicated not-found page. Retired recognition URLs use the existing catch-all, which navigates to `/dashboard`.
- Rewriting the body of archived OpenSpec changes or master-course notes.
- Changing cart checkout, stock rules, payment methods, returns, or gift cards.
- Dropping or rewriting the Metronic layout-38 demo.

## Decisions

- Frontend cleanup removes the unused recognition feature, not product photos.
- Backend source remains; the API answers with withdrawal (410) and deprecation markers.
- Documentation of record is updated. Historical archives and course notes get a banner and keep their original text.
- Retired routes are removed. They are not given a dedicated redirect; the existing catch-all navigates to `/dashboard`.
- Schema stays; no destructive migration.
