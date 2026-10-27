# payment-method-management Specification

## Purpose

Enable configuration and management of payment methods across the multi-location retail system. Payment methods can be assigned to specific points of sale and are validated during sales transactions. This capability supports flexible payment processing and ensures only authorized payment methods are used at each location.

**Integration Points:**
- Integrates with `point-of-sale-management` for payment method assignments
- Integrates with `access-control` for role-based permissions (Admin only)
- Will integrate with future `sales-registration` (EP3) for payment validation

**Deferred Integrations:** See `openspec/DEFERRED_TASKS.md` for EP3 integration tasks.
## Requirements
### Requirement: Payment Method Configuration

The system SHALL allow administrators to configure payment methods available system-wide.

#### Scenario: View all payment methods

- **WHEN** admin requests payment methods list
- **THEN** system returns all payment methods (active and inactive)
- **AND** includes id, code, name, description, isActive
- **AND** results are sorted by name

#### Scenario: Create payment method (future extensibility)

- **WHEN** admin creates new payment method with unique code
- **THEN** system validates code format and uniqueness
- **AND** creates payment method with IsActive=true
- **AND** sets CreatedAt and UpdatedAt timestamps

#### Scenario: Update payment method

- **WHEN** admin updates payment method name or description
- **THEN** system validates changes are valid
- **AND** updates payment method record
- **AND** sets UpdatedAt timestamp

#### Scenario: Activate payment method

- **WHEN** admin activates inactive payment method
- **THEN** system sets IsActive to true
- **AND** payment method becomes available for assignments

#### Scenario: Deactivate payment method

- **WHEN** admin deactivates active payment method
- **THEN** system validates no active assignments exist
- **AND** sets IsActive to false
- **AND** prevents new assignments

### Requirement: Payment Method Code Standards

The system SHALL enforce standard codes for predefined payment methods.

#### Scenario: Predefined payment method codes

- **WHEN** system is initialized
- **THEN** following payment methods are available:
  - CASH (Efectivo)
  - BIZUM (Bizum)
  - TRANSFER (Transferencia bancaria)
  - CARD_OWN (Tarjeta TPV propio)
  - CARD_POS (Tarjeta TPV punto de venta)
  - PAYPAL (PayPal)

#### Scenario: Code format validation

- **WHEN** creating or updating payment method
- **THEN** code must be uppercase alphanumeric with underscores
- **AND** code must be 2-20 characters long
- **AND** code must be unique (case insensitive)

### Requirement: Point of Sale Payment Method Assignment

The system SHALL allow assignment of payment methods to specific points of sale.

#### Scenario: Assign payment method to point of sale

- **WHEN** admin assigns active payment method to active point of sale
- **THEN** system creates PointOfSalePaymentMethod record
- **AND** sets IsActive=true and CreatedAt timestamp
- **AND** payment method becomes available for sales at that location

#### Scenario: Assign already assigned payment method

- **WHEN** admin attempts to assign already active assignment
- **THEN** system returns 409 Conflict
- **AND** provides message "El método de pago ya está asignado a este punto de venta"

#### Scenario: Assign to inactive point of sale

- **WHEN** admin attempts to assign to inactive point of sale
- **THEN** system returns 400 Bad Request
- **AND** provides message "No se puede asignar a un punto de venta inactivo"

#### Scenario: Assign inactive payment method

- **WHEN** admin attempts to assign inactive payment method
- **THEN** system returns 400 Bad Request
- **AND** provides message "No se puede asignar un método de pago inactivo"

### Requirement: Point of Sale Payment Method Management

The system SHALL manage payment method availability per point of sale.

#### Scenario: View assigned payment methods

- **WHEN** admin views payment methods for specific point of sale
- **THEN** system returns assigned payment methods with active status
- **AND** includes payment method details (code, name, description)

#### Scenario: Activate payment method assignment

- **WHEN** admin activates inactive assignment
- **THEN** system sets IsActive to true
- **AND** clears DeactivatedAt timestamp
- **AND** payment method becomes available for sales

#### Scenario: Deactivate payment method assignment

- **WHEN** admin deactivates active assignment
- **THEN** system sets IsActive to false
- **AND** sets DeactivatedAt timestamp
- **AND** payment method is no longer available for new sales

#### Scenario: Unassign payment method

- **WHEN** admin completely removes payment method assignment
- **THEN** system deletes PointOfSalePaymentMethod record
- **AND** payment method is no longer associated with point of sale

### Requirement: Sales Payment Method Validation

The system SHALL validate payment methods during sales transactions.

#### Scenario: Validate payment method availability

- **WHEN** sale is created with payment method and point of sale
- **THEN** system validates payment method is assigned and active for that point of sale
- **AND** allows sale if validation passes

#### Scenario: Reject sale with unavailable payment method

- **WHEN** sale is created with payment method not available at point of sale
- **THEN** system returns 400 Bad Request
- **AND** provides message "El método de pago no está disponible en este punto de venta"

#### Scenario: Allow sale with available payment method

- **WHEN** sale is created with payment method that is active and assigned
- **THEN** system processes sale successfully
- **AND** creates sale record with payment method reference

### Requirement: Authorization Controls

The system SHALL enforce role-based access to payment method operations.

#### Scenario: Admin full access

- **WHEN** authenticated admin performs any payment method operation
- **THEN** system allows operation without restrictions

#### Scenario: Operator restricted access

- **WHEN** operator attempts payment method management operations
- **THEN** system returns 403 Forbidden
- **AND** provides message "Acceso denegado"

#### Scenario: Unauthenticated access

- **WHEN** unauthenticated user accesses payment method endpoints
- **THEN** system returns 401 Unauthorized

### Requirement: Data Integrity and Business Rules

The system SHALL maintain data integrity for payment method operations.

#### Scenario: Prevent deactivation with active sales

- **WHEN** admin attempts to deactivate payment method assignment with recent sales
- **THEN** system returns 400 Bad Request
- **AND** provides message "No se puede desactivar método de pago con ventas recientes"

#### Scenario: Maintain assignment history

- **WHEN** payment method assignment is deactivated then reactivated
- **THEN** system preserves historical DeactivatedAt timestamps
- **AND** creates new active assignment record

#### Scenario: Cascade deactivation

- **WHEN** point of sale is deactivated
- **THEN** system may optionally deactivate all payment method assignments
- **AND** prevents new assignments to deactivated point of sale

### Requirement: Seed Data Management

The system SHALL provide predefined payment methods on initialization, including the system method `GIFT_CARD`. `GIFT_CARD` SHALL be assigned and active on every point of sale, SHALL be hidden from ordinary sale payment choices, and SHALL NOT be deactivated.

#### Scenario: Automatic seed data

- **WHEN** database is initialized or migrated
- **THEN** system creates predefined payment methods if they don't exist
- **AND** sets appropriate names and descriptions in Spanish
- **AND** marks them as active by default
- **AND** creates `GIFT_CARD` when it is missing
- **AND** ensures `GIFT_CARD` is actively assigned to every point of sale

#### Scenario: Seed data idempotency

- **WHEN** seed data runs multiple times
- **THEN** system doesn't create duplicates
- **AND** doesn't modify existing payment method data
- **AND** only adds missing predefined methods
- **AND** does not rename or reprice an existing `GIFT_CARD` method

#### Scenario: Ordinary sale choices hide the gift-card method
- **GIVEN** POS A has cash and `GIFT_CARD` assigned
- **WHEN** the sales form loads payment methods for POS A
- **THEN** cash is selectable
- **AND** `GIFT_CARD` is not selectable

#### Scenario: Reject deactivation of the gift-card method
- **GIVEN** `GIFT_CARD` is assigned to a POS
- **WHEN** an admin deactivates that assignment or the method
- **THEN** the system rejects the request with 400 Bad Request
- **AND** the assignment stays active

