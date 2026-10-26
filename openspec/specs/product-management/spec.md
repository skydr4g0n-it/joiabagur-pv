# product-management Specification

## Purpose

Maintain the global jewelry product catalog with CRUD, photos, search, and bulk import to support sales and recognition.

## Requirements
### Requirement: Manual Product Creation UI
The system SHALL provide a user-friendly form interface for administrators to create individual products with real-time validation and immediate feedback.

#### Scenario: Create product successfully via form
- **WHEN** an administrator navigates to the product creation page
- **AND** fills in SKU "JOY-001", Name "Gold Ring", Price 299.99, and optionally selects a collection
- **AND** submits the form
- **THEN** the product is created successfully
- **AND** a success confirmation is displayed with options to create another product or navigate to the product list

#### Scenario: SKU uniqueness validation in form
- **WHEN** an administrator enters an SKU that already exists
- **THEN** the form displays a validation error "El SKU ya está en uso"
- **AND** the submit button is disabled until a unique SKU is entered

#### Scenario: Required field validation
- **WHEN** an administrator attempts to submit the form without filling required fields (SKU, Name, Price)
- **THEN** the form displays validation messages for each missing field
- **AND** the form is not submitted

#### Scenario: Price validation
- **WHEN** an administrator enters a price <= 0
- **THEN** the form displays a validation error for the price field
- **AND** the submit button is disabled until a valid price is entered

#### Scenario: Collection dropdown population
- **WHEN** an administrator opens the product creation page
- **THEN** the collection dropdown is populated with available collections from the API
- **AND** selecting a collection is optional

#### Scenario: Form loading states
- **WHEN** the form is being submitted
- **THEN** a loading indicator is displayed
- **AND** form inputs are disabled to prevent duplicate submissions

#### Scenario: API error handling
- **WHEN** the product creation API returns an error
- **THEN** the error message is displayed to the user
- **AND** the form remains editable for correction

### Requirement: Product Creation API Testing
The system SHALL have comprehensive integration tests for the POST /api/products endpoint verifying all business rules and security requirements.

#### Scenario: Integration test coverage
- **WHEN** integration tests are executed for product creation
- **THEN** they verify successful creation, validation errors, SKU uniqueness, authentication, and authorization
- **AND** use Testcontainers for real database operations

### Requirement: Product Catalog Listing API
The system SHALL provide a paginated product catalog endpoint with role-based filtering: administrators see all products, operators see only products with Inventory records at their assigned points of sale. **Product photos SHALL include accessible URL fields for display in UI.**

#### Scenario: Administrator retrieves full product catalog
- **WHEN** an authenticated administrator requests GET /api/products with page=1, pageSize=50
- **THEN** the system returns a paginated result with up to 50 products from the global Product table
- **AND** includes pagination metadata (totalCount, totalPages, currentPage)
- **AND** each product includes Id, SKU, Name, Price, PrimaryPhotoUrl, and AvailableQuantity
- **AND** PrimaryPhotoUrl is a complete, accessible URL (not just filename) if a primary photo exists

#### Scenario: Operator retrieves filtered product catalog
- **WHEN** an authenticated operator requests GET /api/products with page=1, pageSize=50
- **THEN** the system returns ONLY products that have Inventory records at operator's assigned points of sale
- **AND** includes products with Quantity = 0 if Inventory record exists
- **AND** excludes products with no Inventory records at assigned POS
- **AND** aggregates quantities from all assigned POS for multi-POS operators

#### Scenario: Sort products by name
- **WHEN** an authenticated user requests GET /api/products?sortBy=Name
- **THEN** the products are returned sorted alphabetically by name (filtered by role)

#### Scenario: Sort products by creation date
- **WHEN** an authenticated user requests GET /api/products?sortBy=CreatedAt
- **THEN** the products are returned sorted by creation date (filtered by role)

#### Scenario: Navigate to next page
- **WHEN** an authenticated user requests GET /api/products?page=2&pageSize=50
- **THEN** the system returns products 51-100 with correct pagination metadata (filtered by role)

#### Scenario: Operator with no assigned products
- **WHEN** an operator has no products in Inventory at assigned points of sale
- **THEN** GET /api/products returns an empty array with totalCount=0

#### Scenario: Require authentication for catalog access
- **WHEN** an unauthenticated user requests GET /api/products
- **THEN** the request is rejected with 401 Unauthorized

### Requirement: Product Search API
The system SHALL provide a search endpoint that performs SKU exact match and name partial match with role-based filtering: administrators search all products, operators search only products with Inventory records at their assigned points of sale. **Product photos in search results SHALL include accessible URL fields.**

#### Scenario: Administrator searches by exact SKU match
- **WHEN** an authenticated administrator requests GET /api/products/search?query=JOY-001
- **AND** a product with SKU "JOY-001" exists in the global catalog
- **THEN** the system returns the matching product with its primary photo
- **AND** the primary photo URL is a complete, accessible URL (not just filename)

#### Scenario: Operator searches by exact SKU match in assigned inventory
- **WHEN** an authenticated operator requests GET /api/products/search?query=JOY-001
- **AND** a product with SKU "JOY-001" has Inventory records at operator's assigned POS
- **THEN** the system returns the matching product with its primary photo and quantity
- **AND** the primary photo URL is a complete, accessible URL if photo exists

#### Scenario: Operator searches for product not in assigned inventory
- **WHEN** an authenticated operator requests GET /api/products/search?query=JOY-999
- **AND** a product with SKU "JOY-999" exists but has NO Inventory records at operator's assigned POS
- **THEN** the system returns an empty array (product is hidden from operator)

#### Scenario: Administrator searches by partial name match
- **WHEN** an authenticated administrator requests GET /api/products/search?query=Anillo
- **AND** products with names containing "Anillo" exist (case-insensitive)
- **THEN** the system returns all matching products from global catalog

#### Scenario: Operator searches by partial name match
- **WHEN** an authenticated operator requests GET /api/products/search?query=Anillo
- **AND** products with names containing "Anillo" exist
- **THEN** the system returns ONLY matching products that have Inventory records at assigned POS

#### Scenario: Search returns no results
- **WHEN** an authenticated user searches for a term that matches no accessible products
- **THEN** the system returns an empty array (not 404)

#### Scenario: Search with minimum query length
- **WHEN** an authenticated user provides a query with less than 2 characters
- **THEN** the request is rejected with 400 Bad Request and validation error

#### Scenario: Search result limit
- **WHEN** a search query matches more than 50 accessible products
- **THEN** only the first 50 results are returned (filtered by role)

#### Scenario: Require authentication for search
- **WHEN** an unauthenticated user requests the search endpoint
- **THEN** the request is rejected with 401 Unauthorized

### Requirement: Product Photo Deletion API
The system SHALL provide an endpoint for deleting product photos with automatic file cleanup and primary photo reassignment. This operation is restricted to administrators only.

#### Scenario: Delete non-primary photo successfully
- **WHEN** an authenticated administrator DELETEs /api/products/{id}/photos/{photoId} for a non-primary photo
- **THEN** the photo file is removed from storage via IFileStorageService
- **AND** the ProductPhoto record is deleted from the database
- **AND** the operation returns 204 No Content

#### Scenario: Delete primary photo
- **WHEN** an authenticated administrator deletes the primary photo
- **AND** other photos exist for the product
- **THEN** the photo is deleted and another photo is automatically designated as primary
- **AND** the operation returns 204 No Content

#### Scenario: Delete only photo for product
- **WHEN** an authenticated administrator deletes the only photo for a product
- **THEN** the photo is deleted successfully
- **AND** no other photo is designated as primary

#### Scenario: Delete photo from non-existent product
- **WHEN** an authenticated administrator attempts to DELETE /api/products/{id}/photos/{photoId} with non-existent product ID
- **THEN** the system returns 404 Not Found

#### Scenario: Delete non-existent photo
- **WHEN** an authenticated administrator attempts to delete a photo that does not exist
- **THEN** the system returns 404 Not Found

#### Scenario: Unauthorized photo deletion
- **WHEN** an operator or unauthenticated user attempts to delete a photo
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Product Photo Primary Designation API
The system SHALL provide an endpoint for changing the primary photo of a product. This operation is restricted to administrators only.

#### Scenario: Set primary photo successfully
- **WHEN** an authenticated administrator PUTs to /api/products/{id}/photos/{photoId}/primary
- **THEN** the specified photo has IsPrimary set to true
- **AND** all other photos for that product have IsPrimary set to false
- **AND** the operation returns 200 OK

#### Scenario: Set primary on already primary photo
- **WHEN** an authenticated administrator sets a photo as primary that is already primary
- **THEN** the operation succeeds with no changes
- **AND** returns 200 OK

#### Scenario: Set primary on non-existent product
- **WHEN** an authenticated administrator attempts to set primary photo for non-existent product
- **THEN** the system returns 404 Not Found

#### Scenario: Set primary on non-existent photo
- **WHEN** an authenticated administrator attempts to set a non-existent photo as primary
- **THEN** the system returns 404 Not Found

#### Scenario: Unauthorized primary designation
- **WHEN** an operator or unauthenticated user attempts to set primary photo
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Product Catalog Frontend
The system SHALL provide a user interface for browsing the product catalog with pagination and visual product cards. Content is filtered by the backend based on user role (admin sees all, operator sees only assigned products).

#### Scenario: Display product catalog page
- **WHEN** an authenticated user navigates to the product catalog page
- **THEN** products are displayed in a grid or card layout
- **AND** each card shows SKU, name, price, quantity (if operator), and primary photo thumbnail
- **AND** pagination controls are displayed at the bottom
- **AND** products with quantity = 0 display a warning badge or indicator

#### Scenario: Navigate through pages
- **WHEN** an authenticated user clicks the next page button
- **THEN** the next page of products is loaded and displayed
- **AND** the current page indicator is updated

#### Scenario: Navigate to product edit
- **WHEN** an authenticated administrator clicks on a product card
- **THEN** the user is navigated to the product edit page

#### Scenario: Empty catalog display
- **WHEN** no products exist in the catalog
- **THEN** an empty state message is displayed
- **AND** prompts the user to import or create products

#### Scenario: Catalog loading state
- **WHEN** the catalog is being loaded
- **THEN** skeleton loaders are displayed in the card layout

#### Scenario: Mobile responsive catalog
- **WHEN** an authenticated user views the catalog on mobile
- **THEN** the layout adjusts to a single column with responsive cards

### Requirement: Product Search Frontend
The system SHALL provide a search interface integrated into the product catalog for real-time product lookup. Search results are filtered by the backend based on user role.

#### Scenario: Search with real-time filtering
- **WHEN** an authenticated user types in the search input
- **THEN** the search is triggered after 300ms debounce delay
- **AND** matching accessible products are displayed replacing or filtering the catalog
- **AND** products with quantity = 0 display a warning indicator

#### Scenario: Display SKU exact match prominently
- **WHEN** a search matches a product by exact SKU
- **THEN** the matching product is displayed first or highlighted

#### Scenario: Display partial name matches
- **WHEN** a search matches products by partial name
- **THEN** all matching products are displayed in the catalog

#### Scenario: Clear search results
- **WHEN** an authenticated user clicks the clear search button
- **THEN** the search query is cleared
- **AND** the full catalog is displayed again

#### Scenario: No search results
- **WHEN** a search returns no matching products
- **THEN** a "No results found" message is displayed
- **AND** suggests trying different search terms

#### Scenario: Search loading indicator
- **WHEN** a search is in progress
- **THEN** a loading indicator is displayed in the search input

### Requirement: Product Photo Management Frontend
The system SHALL provide UI controls for deleting and designating primary photos in the product edit page. These controls are visible and functional only for administrators.

#### Scenario: Delete photo with confirmation
- **WHEN** an administrator clicks the delete button on a photo
- **THEN** a confirmation dialog is displayed
- **AND** upon confirmation, the photo is deleted via DELETE endpoint
- **AND** the photo gallery is refreshed

#### Scenario: Photo management controls hidden for operators
- **WHEN** an operator views the product edit page (if accessible)
- **THEN** photo management controls (delete, set primary) are hidden
- **AND** photos are displayed in read-only mode

#### Scenario: Set primary photo
- **WHEN** an administrator clicks the "set as primary" button on a photo
- **THEN** the photo is marked as primary via PUT endpoint
- **AND** the primary indicator (badge/star) moves to the selected photo

#### Scenario: Photo management loading states
- **WHEN** a photo operation (delete, set primary) is in progress
- **THEN** the UI shows a loading indicator on the affected photo
- **AND** prevents additional operations until completion

#### Scenario: Photo management error handling
- **WHEN** a photo operation fails
- **THEN** an error toast notification is displayed
- **AND** the gallery state is reverted or refreshed

### Requirement: Product Detail Endpoint Returns Photo URLs
The system SHALL return complete photo information including accessible URLs when retrieving individual product details via GET /api/products/{id}.

#### Scenario: Get product with photos
- **WHEN** an authenticated user requests GET /api/products/{id}
- **AND** the product has uploaded photos
- **THEN** the response includes a Photos array
- **AND** each photo object contains Id, ProductId, FileName, Url, DisplayOrder, IsPrimary, CreatedAt, UpdatedAt
- **AND** the Url field contains a complete, accessible URL constructed via IFileStorageService
- **AND** photos are ordered by DisplayOrder

#### Scenario: Get product without photos
- **WHEN** an authenticated user requests GET /api/products/{id}
- **AND** the product has no uploaded photos
- **THEN** the response includes an empty Photos array
- **AND** no errors are returned

#### Scenario: Photo URLs are accessible
- **WHEN** a product detail response includes photo URLs
- **THEN** each URL can be used directly in an HTML <img> src attribute
- **AND** URLs point to the correct storage location (local filesystem or cloud storage)
- **AND** URLs follow the format returned by IFileStorageService.GetUrlAsync()

### Requirement: Product Entity Management
The system SHALL maintain Product entities with unique SKU identifiers, name, description, price, optional collection assignment, and active status.

#### Scenario: Create product with valid data
- **WHEN** a product is created with SKU "JOY-001", Name "Gold Ring", Price 299.99
- **THEN** the product is stored with a unique ID, IsActive = true, and audit timestamps

#### Scenario: SKU uniqueness validation
- **WHEN** attempting to create a product with an existing SKU "JOY-001"
- **THEN** the system rejects the creation with a validation error

#### Scenario: Price validation
- **WHEN** attempting to create a product with Price <= 0
- **THEN** the system rejects the creation with a validation error

### Requirement: Product Photo Management
The system SHALL support multiple photos per product with display ordering and primary photo designation.

#### Scenario: Associate photo with product
- **WHEN** a photo is uploaded for product "JOY-001"
- **THEN** the photo is stored with DisplayOrder and linked to the product

#### Scenario: Primary photo designation
- **WHEN** a photo is marked as primary for a product
- **THEN** any existing primary photo for that product is unmarked
- **AND** the new photo becomes the primary photo

#### Scenario: Multiple photos per product
- **WHEN** multiple photos are uploaded for a product
- **THEN** each photo has a unique DisplayOrder for sorting

### Requirement: Collection Management
The system SHALL support product categorization through Collections with name and description.

#### Scenario: Create collection
- **WHEN** a collection is created with Name "Summer 2024"
- **THEN** the collection is stored and available for product assignment

#### Scenario: Assign product to collection
- **WHEN** a product is assigned to collection "Summer 2024"
- **THEN** the product's CollectionId references the collection

### Requirement: Excel Product Import
The system SHALL support bulk product import from Excel files (.xlsx, .xls) with validation, UPSERT logic, and atomic transactions.

#### Scenario: Import new products successfully
- **WHEN** an administrator uploads an Excel file with products having new SKUs
- **AND** all data is valid (SKU, Name required; Price > 0)
- **THEN** all products are created with IsActive = true
- **AND** the import result shows the count of created products

#### Scenario: Update existing products
- **WHEN** an administrator imports products with SKUs that already exist
- **THEN** the existing products are updated with new Name, Description, Price, Collection values
- **AND** the product ID and associated photos are preserved
- **AND** UpdatedAt timestamp is refreshed

#### Scenario: Mixed create and update
- **WHEN** an Excel file contains both new and existing SKUs
- **THEN** new products are created and existing products are updated
- **AND** the import result shows separate counts for created and updated

#### Scenario: Validation errors before import
- **WHEN** an Excel file contains validation errors (empty SKU, invalid price, missing required fields)
- **THEN** the system returns a list of errors with row numbers
- **AND** no products are imported until errors are corrected

#### Scenario: Duplicate SKU detection in file
- **WHEN** an Excel file contains the same SKU in multiple rows
- **THEN** the system detects the duplicate
- **AND** returns an error "SKU duplicado en el archivo: [SKU]"
- **AND** prevents import until duplicates are removed

#### Scenario: Automatic collection creation
- **WHEN** an Excel file references a collection name that does not exist
- **THEN** the system automatically creates the collection
- **AND** assigns the product to the newly created collection

#### Scenario: Transaction atomicity
- **WHEN** an error occurs during import processing
- **THEN** all changes are rolled back
- **AND** no partial data is persisted

### Requirement: Product Import API
The system SHALL provide REST API endpoints for Excel template download and file upload with proper authentication and file validation.

#### Scenario: Download Excel template as administrator
- **WHEN** an authenticated administrator GETs /api/products/import-template
- **THEN** the system returns an Excel file with exact column headers and example data
- **AND** file has appropriate content-type header for Excel download

#### Scenario: Upload Excel file as administrator
- **WHEN** an authenticated administrator POSTs to /api/products/import with a valid Excel file
- **THEN** the system validates all rows before processing any
- **AND** shows all validation errors before import confirmation
- **AND** processes valid rows only after user confirmation
- **AND** returns ImportResult with success/error details

#### Scenario: Unauthorized import attempt
- **WHEN** an operator or unauthenticated user attempts to POST to /api/products/import
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

#### Scenario: Invalid file format
- **WHEN** a file with format other than .xlsx or .xls is uploaded
- **THEN** the request is rejected with 400 Bad Request and error message

#### Scenario: File size limit exceeded
- **WHEN** a file larger than 10MB is uploaded
- **THEN** the request is rejected with 413 Payload Too Large

### Requirement: File Storage Service
The system SHALL provide an abstraction for file storage that supports local development and cloud production environments.

#### Scenario: Store file locally in development
- **WHEN** running in development environment
- **AND** a file is uploaded
- **THEN** the file is stored in the local filesystem under ./uploads/

#### Scenario: Store file in cloud in production
- **WHEN** running in production environment
- **AND** a file is uploaded
- **THEN** the file is stored in the configured cloud storage (S3/Azure Blob)

#### Scenario: Generate unique filenames
- **WHEN** a file is uploaded
- **THEN** a unique filename is generated to prevent conflicts

#### Scenario: File format validation
- **WHEN** a file upload is attempted
- **THEN** only allowed formats (JPG, PNG for photos; XLSX, XLS for Excel) are accepted

### Requirement: Product Import Frontend
The system SHALL provide a user-friendly interface for bulk product import with preview, validation feedback, and results display.

#### Scenario: Drag and drop file upload
- **WHEN** an administrator navigates to the product import page
- **THEN** a drag-and-drop zone is displayed for Excel file selection

#### Scenario: Download Excel template
- **WHEN** an administrator requests product import template
- **THEN** system provides downloadable Excel template file via GET /api/products/import-template endpoint
- **AND** template contains exact column headers: "SKU", "Name", "Description", "Price", "Collection" (header row protected/locked)
- **AND** template includes example row with sample data
- **AND** template includes data validation rules (Price > 0, SKU text format, Name required)
- **AND** template includes instructions or comments explaining format requirements
- **AND** template has proper formatting (bold headers, number format for Price column, text format for SKU)

#### Scenario: Template accessible from help documentation
- **WHEN** administrator accesses help or documentation pages
- **THEN** template download link is available
- **AND** link provides same template as import page

#### Scenario: Preview before import
- **WHEN** a valid Excel file is selected (before upload)
- **THEN** the system shows a preview with row count and basic validation status
- **AND** displays preview table showing first few rows that will be imported

#### Scenario: Display validation errors
- **WHEN** the uploaded file has validation errors
- **THEN** errors are displayed with detailed format: row number, field name, and error message
- **AND** errors are grouped by type (missing columns, invalid data, business rule violations)
- **AND** example error format: "Row 5: SKU 'ABC-123' is duplicate" or "Row 8: Price must be greater than 0"
- **AND** the import button is disabled until errors are resolved

#### Scenario: Confirm import action with summary
- **WHEN** the file is valid and the administrator clicks import
- **THEN** a confirmation dialog is shown before processing
- **AND** dialog displays summary: total rows to process, breakdown (e.g., "X products will be created, Y products will be updated")
- **AND** requires explicit confirmation before processing

#### Scenario: Display import progress
- **WHEN** an import is in progress
- **THEN** a progress indicator is shown to the user
- **AND** import button is disabled during processing

#### Scenario: Display import results
- **WHEN** an import completes
- **THEN** a summary is displayed showing created count, updated count, and any warnings

### Requirement: Product Update API
The system SHALL provide a REST API endpoint for updating existing products with SKU immutability enforcement.

#### Scenario: Update product successfully
- **WHEN** an authenticated administrator PUTs to /api/products/{id} with valid data (Name, Description, Price, CollectionId)
- **THEN** the product is updated with the new values
- **AND** UpdatedAt timestamp is refreshed
- **AND** the updated product is returned

#### Scenario: SKU immutability enforcement
- **WHEN** an administrator attempts to update a product's SKU
- **THEN** the system rejects the request with 400 Bad Request
- **AND** returns error message "SKU cannot be modified"

#### Scenario: Update with invalid price
- **WHEN** an administrator attempts to update a product with Price <= 0
- **THEN** the system rejects the request with 400 Bad Request
- **AND** returns validation error

#### Scenario: Update non-existent product
- **WHEN** an administrator attempts to PUT to /api/products/{id} with non-existent ID
- **THEN** the system returns 404 Not Found

#### Scenario: Unauthorized update attempt
- **WHEN** an operator or unauthenticated user attempts to PUT to /api/products/{id}
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Product Update Frontend
The system SHALL provide a user interface for editing existing products with pre-populated form fields and SKU immutability.

#### Scenario: Load product for editing
- **WHEN** an administrator navigates to the product edit page for an existing product
- **THEN** the form is pre-populated with current product data (SKU, Name, Description, Price, Collection)

#### Scenario: SKU field disabled
- **WHEN** the product edit form is displayed
- **THEN** the SKU field is disabled and visually indicated as non-editable
- **AND** the SKU value is displayed but cannot be modified

#### Scenario: Update product successfully
- **WHEN** an administrator modifies editable fields and submits the form
- **THEN** the product is updated via PUT /api/products/{id}
- **AND** a success message is displayed
- **AND** the user is redirected to the product list or detail page

#### Scenario: Validation errors on update
- **WHEN** an administrator submits invalid data (empty name, negative price)
- **THEN** validation errors are displayed inline
- **AND** the form is not submitted until errors are corrected

#### Scenario: Product not found
- **WHEN** an administrator attempts to edit a non-existent product
- **THEN** a "Product not found" message is displayed
- **AND** the user is redirected to the product list

### Requirement: Product Photo Upload API
The system SHALL provide a REST API endpoint for uploading product photos with format validation and storage.

#### Scenario: Upload photo successfully
- **WHEN** an authenticated administrator POSTs to /api/products/{id}/photos with a valid JPG or PNG file
- **THEN** the photo is stored using IFileStorageService
- **AND** a ProductPhoto record is created with DisplayOrder
- **AND** if no primary photo exists, IsPrimary is set to true
- **AND** the photo information is returned

#### Scenario: Upload multiple photos
- **WHEN** an administrator uploads multiple photos for a product
- **THEN** each photo is stored with an incremented DisplayOrder
- **AND** the photos are returned in display order

#### Scenario: Invalid photo format
- **WHEN** an administrator attempts to upload a file that is not JPG or PNG
- **THEN** the request is rejected with 400 Bad Request
- **AND** returns error message "Only JPG and PNG formats are allowed"

#### Scenario: Photo size limit exceeded
- **WHEN** an administrator attempts to upload a photo larger than 5MB
- **THEN** the request is rejected with 413 Payload Too Large

#### Scenario: Upload photo to non-existent product
- **WHEN** an administrator attempts to POST to /api/products/{id}/photos with non-existent product ID
- **THEN** the system returns 404 Not Found

#### Scenario: Unauthorized photo upload
- **WHEN** an operator or unauthenticated user attempts to upload a photo
- **THEN** the request is rejected with 401 Unauthorized or 403 Forbidden

### Requirement: Product Photo Management Service
The system SHALL provide business logic for photo management including primary designation and display ordering.

#### Scenario: Automatic primary designation
- **WHEN** the first photo is uploaded for a product
- **THEN** IsPrimary is automatically set to true

#### Scenario: Primary photo designation
- **WHEN** a photo is marked as primary
- **THEN** any existing primary photo for that product has IsPrimary set to false
- **AND** the selected photo has IsPrimary set to true

#### Scenario: Display order management
- **WHEN** photos are uploaded
- **THEN** each photo receives a unique DisplayOrder value
- **AND** DisplayOrder is used for sorting in photo galleries

#### Scenario: Photo deletion
- **WHEN** a photo is deleted
- **THEN** the file is removed from storage via IFileStorageService
- **AND** the ProductPhoto record is removed from the database
- **AND** if it was the primary photo, another photo is automatically designated as primary

### Requirement: Product Photo Upload Frontend
The system SHALL provide a user interface for uploading product photos with drag-and-drop, preview, and validation.

#### Scenario: Photo upload component
- **WHEN** an administrator is on the product edit page
- **THEN** a photo upload component is displayed with drag-and-drop zone

#### Scenario: Drag and drop photo upload
- **WHEN** an administrator drags and drops a JPG or PNG file
- **THEN** the file is validated and uploaded via POST /api/products/{id}/photos
- **AND** a preview thumbnail is displayed

#### Scenario: Multiple photo upload
- **WHEN** an administrator uploads multiple photos
- **THEN** all photos are uploaded and displayed in the gallery
- **AND** photos are shown in DisplayOrder

#### Scenario: Photo format validation
- **WHEN** an administrator attempts to upload an invalid format
- **THEN** an error message is displayed
- **AND** the upload is prevented

#### Scenario: Primary photo indication
- **WHEN** photos are displayed in the gallery
- **THEN** the primary photo is visually indicated (e.g., with a badge or border)

#### Scenario: Photo upload progress
- **WHEN** a photo is being uploaded
- **THEN** a progress indicator is shown
- **AND** the upload can be cancelled if needed

### Requirement: Price Display Format

The system SHALL display all product prices using Euro (EUR) currency format with Spanish locale conventions throughout the product interfaces.

#### Scenario: Display product prices in Euro format
- **WHEN** displaying product prices in catalog, search results, or import preview
- **THEN** the € symbol is shown before the numeric value
- **AND** prices are formatted with 2 decimal places (e.g., €299.99)
- **AND** Spanish locale (es-ES) formatting is used when using toLocaleString
