## MODIFIED Requirements

### Requirement: Product Photo Upload Frontend
The system SHALL provide a user interface for uploading product photos with drag-and-drop, preview, and validation. The interface SHALL describe the photos as product catalog images. It SHALL NOT describe them as recognition references and SHALL NOT generate embeddings or load a recognition model while uploading or deleting photos.

#### Scenario: Photo upload component
- **GIVEN** an administrator on the product edit page
- **WHEN** the page is shown
- **THEN** a photo upload component is displayed with a drag-and-drop zone
- **AND** the visible description does not mention image recognition

#### Scenario: Drag and drop photo upload
- **GIVEN** an administrator
- **WHEN** the administrator drags and drops a JPG or PNG file
- **THEN** the file is validated and uploaded via POST /api/products/{id}/photos
- **AND** a preview thumbnail is displayed
- **AND** no request is sent to `/api/image-recognition`

#### Scenario: Multiple photo upload
- **GIVEN** an administrator
- **WHEN** the administrator uploads multiple photos
- **THEN** all photos are uploaded and displayed in the gallery
- **AND** photos are shown in DisplayOrder

#### Scenario: Photo format validation
- **GIVEN** an administrator
- **WHEN** the administrator attempts to upload an invalid format
- **THEN** an error message is displayed
- **AND** the upload is prevented

#### Scenario: Primary photo indication
- **GIVEN** photos displayed in the gallery
- **WHEN** the gallery renders
- **THEN** the primary photo is visually indicated (for example with a badge or border)

#### Scenario: Photo upload progress
- **GIVEN** a photo upload in progress
- **WHEN** the file is uploading
- **THEN** a progress indicator is shown
- **AND** the upload can be cancelled if needed
