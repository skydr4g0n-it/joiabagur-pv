# user-management Specification

## Purpose

Let administrators create and maintain user accounts, roles, POS assignments, and account status for the multi-location system.

## Requirements
### Requirement: User Creation

The system SHALL allow administrators to create new users with specified roles.

#### Scenario: Create operator successfully

- **WHEN** admin creates user with valid data and Operator role
- **THEN** system validates username is unique
- **AND** validates email is unique (if provided)
- **AND** hashes password with BCrypt
- **AND** creates user with IsActive=true
- **AND** sets CreatedAt and UpdatedAt timestamps
- **AND** returns created user data (without password)

#### Scenario: Create administrator successfully

- **WHEN** admin creates user with valid data and Admin role
- **THEN** system creates user with Admin role
- **AND** user has full system access without point of sale assignments

#### Scenario: Create user with duplicate username

- **WHEN** admin creates user with existing username
- **THEN** system returns 409 Conflict
- **AND** provides message "El nombre de usuario ya está en uso"

#### Scenario: Create user with duplicate email

- **WHEN** admin creates user with email that already exists
- **THEN** system returns 409 Conflict
- **AND** provides message "El email ya está registrado"

#### Scenario: Create user with weak password

- **WHEN** admin creates user with password less than 8 characters
- **THEN** system returns 400 Bad Request
- **AND** provides validation message "La contraseña debe tener al menos 8 caracteres"

#### Scenario: Create user with missing required fields

- **WHEN** admin creates user without username, password, firstName, lastName, or role
- **THEN** system returns 400 Bad Request
- **AND** provides validation errors for each missing field

#### Scenario: Operator attempts to create user

- **WHEN** operator attempts to create user
- **THEN** system returns 403 Forbidden
- **AND** provides message "Acceso denegado"

### Requirement: User Modification

The system SHALL allow administrators to modify existing user information.

#### Scenario: Update user basic information

- **WHEN** admin updates user firstName, lastName, or email
- **THEN** system validates email uniqueness (excluding current user)
- **AND** updates user record
- **AND** sets UpdatedAt timestamp
- **AND** returns updated user data

#### Scenario: Change user role

- **WHEN** admin changes user role from Operator to Admin
- **THEN** system updates user role
- **AND** existing point of sale assignments remain but are no longer enforced

#### Scenario: Deactivate user

- **WHEN** admin sets user IsActive to false
- **THEN** system updates IsActive flag
- **AND** deactivated user cannot login
- **AND** user appears as inactive in user list

#### Scenario: Reactivate user

- **WHEN** admin sets user IsActive to true
- **THEN** system updates IsActive flag
- **AND** reactivated user can login again

#### Scenario: Update with duplicate email

- **WHEN** admin updates user email to one already used by another user
- **THEN** system returns 409 Conflict
- **AND** provides message "El email ya está registrado"

#### Scenario: Username immutability

- **WHEN** admin attempts to change username
- **THEN** system rejects the change
- **AND** username remains unchanged
- **AND** provides message "El nombre de usuario no puede modificarse"

#### Scenario: Update non-existent user

- **WHEN** admin attempts to update user that doesn't exist
- **THEN** system returns 404 Not Found

#### Scenario: Operator attempts to update user

- **WHEN** operator attempts to update any user
- **THEN** system returns 403 Forbidden

### Requirement: Password Management

The system SHALL allow administrators to change user passwords.

#### Scenario: Admin changes user password

- **WHEN** admin changes another user's password
- **THEN** system hashes new password with BCrypt
- **AND** updates password hash
- **AND** sets UpdatedAt timestamp
- **AND** returns 204 No Content

#### Scenario: Password change with weak password

- **WHEN** admin sets password less than 8 characters
- **THEN** system returns 400 Bad Request
- **AND** provides validation message

### Requirement: User Listing

The system SHALL allow administrators to view all users.

#### Scenario: List all users

- **WHEN** admin requests user list
- **THEN** system returns all users (active and inactive)
- **AND** includes id, username, firstName, lastName, email, role, isActive
- **AND** does not include password hash
- **AND** results are paginated

#### Scenario: Get single user details

- **WHEN** admin requests specific user by ID
- **THEN** system returns user details
- **AND** includes assigned point of sales (for operators)

#### Scenario: Operator attempts to list users

- **WHEN** operator attempts to list users
- **THEN** system returns 403 Forbidden

### Requirement: User Validation Rules

The system SHALL enforce validation rules for user data.

#### Scenario: Username validation

- **WHEN** creating or updating user
- **THEN** username must be at least 3 characters
- **AND** username must be alphanumeric with underscores allowed
- **AND** username must be unique

#### Scenario: Email validation

- **WHEN** email is provided
- **THEN** email must be valid format
- **AND** email must be unique (if provided)

#### Scenario: Name validation

- **WHEN** creating or updating user
- **THEN** firstName is required and non-empty
- **AND** lastName is required and non-empty

