## 1. Withdraw the recognition API

- [x] 1.1 Add an action filter on `ImageRecognitionController` that returns 410 Gone with code `image_recognition_withdrawn` and a Spanish withdrawal message, without executing the action. Remove action-level `Authorize(Roles = "Administrator")` attributes and keep the class-level `[Authorize]`. Mark the controller, `IImageRecognitionService`, and `IModelHealthService` with `[Obsolete]` and XML remarks. Leave method bodies, DI registration, and schema unchanged. Validate with `dotnet build` on the API project and confirm no new migration file exists.

- [x] 1.2 Update `ImageRecognitionControllerTests` and `EmbeddingEndpointsTests` so authenticated calls, including operator calls that previously expected 403, expect 410, and unauthenticated calls expect 401. Name new or renamed tests `Method_Scenario_ExpectedResult`. Do not delete service unit tests in `ImageRecognitionEmbeddingServiceTests`. Validate with `dotnet test --filter "FullyQualifiedName~ImageRecognition|FullyQualifiedName~EmbeddingEndpoints"`.

## 2. Remove the recognition UI

- [x] 2.1 Delete the model-health toast, `/admin/ai-model`, `/sales/new/image`, recognition and training services, recognition-only types, and their unit tests. Remove those routes, the "Modelo de IA" menu item, and the image-recognition client inside `sales.service` while keeping sales methods. Remove `@tensorflow/tfjs` and the TensorFlow test setup only after no remaining source file imports them. Leave the layout-38 demo selector in place. Validate with a search that `frontend/src` no longer imports `@tensorflow/tfjs` or `image-recognition.service`, then run the frontend unit tests and `npm run build`.

- [x] 2.2 Remove feature extraction, embedding requests, and recognition wording from `product-photo-upload.tsx`. Keep drag-and-drop upload, JPG/PNG checks, primary photo, and delete through the product photo API. Update `product-photo-upload.test.tsx` so tests use `should [behavior] when [condition]` and cover upload without an embeddings call. Validate with `npm test -- src/pages/products/components/product-photo-upload.test.tsx`.

## 3. Cover the retired screens

- [x] 3.1 Add `frontend/e2e/retired-image-recognition.spec.ts` using the authenticated-session setup from `frontend/e2e/gift-cards.spec.ts`. Assert: `should open the dashboard when visiting a retired recognition route` for `/admin/ai-model` and `/sales/new/image`, and `should omit Modelo de IA when the administrator sidebar is shown`. Validate with the Playwright run for that file.

## 4. Update current documentation

- [x] 4.1 Edit `README.md`, `Documentos/epicas.md`, `HU-EP3-001`, `HU-EP3-002`, `HU-EP4-001`, `HU-EP1-004` when it presents photos as recognition references, `Documentos/Guias/ventas-registro.md`, and `Documentos/Guias/admin-modelo-ia.md` so recognition is withdrawn and manual sales remain. Keep entity descriptions in `modelo-de-datos.md`, `arquitectura.md`, and `modelo-c4.md`, and state that the app no longer uses them for recognition. Do not add a new epic. Validate by searching those files for active instructions to train a model or open `/admin/ai-model`.

## 5. Banner historical documents

- [x] 5.1 Add the English withdrawal banner from `design.md` as the first line of each markdown file under the archived OpenSpec changes for image recognition and embedding similarity. Add the Spanish banner to historical product notes (`Documentos/prompts.md` and proposal notes that describe this feature as current) and to master-course files only when they describe Joiabagur product-photo recognition, not generic model lessons. Do not edit the bodies. Validate by opening one archived proposal and one master note and confirming the banner is first and the following paragraph is unchanged.
