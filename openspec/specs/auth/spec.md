# auth Specification

## Purpose

Authenticate users with username and password, issue JWT access and refresh tokens, and manage session security for the API.

## Requirements
### Requirement: User Login

The system SHALL authenticate users with username and password, returning a valid session upon successful authentication.

#### Scenario: Successful login as Administrator

- **WHEN** user submits valid admin credentials
- **THEN** system validates credentials against database
- **AND** updates LastLoginAt timestamp
- **AND** generates JWT access token with role claim
- **AND** generates refresh token stored in database
- **AND** sets HTTP-only cookies for both tokens
- **AND** returns user information (id, username, firstName, lastName, role)

#### Scenario: Successful login as Operator

- **WHEN** user submits valid operator credentials
- **THEN** system validates credentials against database
- **AND** updates LastLoginAt timestamp
- **AND** generates JWT access token with role claim
- **AND** generates refresh token stored in database
- **AND** sets HTTP-only cookies for both tokens
- **AND** returns user information including assigned point of sales

#### Scenario: Login with invalid credentials

- **WHEN** user submits invalid username or password
- **THEN** system returns 401 Unauthorized
- **AND** provides generic error message "Usuario o contraseña incorrectos"
- **AND** does not reveal whether username or password was incorrect
- **AND** logs failed attempt for security monitoring

#### Scenario: Login with inactive user

- **WHEN** user with IsActive=false submits correct credentials
- **THEN** system returns 401 Unauthorized
- **AND** provides message "Usuario desactivado. Contacte al administrador"
- **AND** does not generate any tokens

#### Scenario: Login with missing fields

- **WHEN** user submits login request without username or password
- **THEN** system returns 400 Bad Request
- **AND** provides validation error details

### Requirement: JWT Token Management

The system SHALL manage JWT access tokens and refresh tokens for secure session handling.

#### Scenario: Access token structure

- **WHEN** access token is generated
- **THEN** token includes user ID claim
- **AND** token includes username claim
- **AND** token includes role claim (Admin or Operator)
- **AND** token has 1-hour expiration
- **AND** token is signed with configured secret key

#### Scenario: Refresh token storage

- **WHEN** refresh token is generated
- **THEN** token is stored in database with user reference
- **AND** token has 8-hour expiration
- **AND** token can be revoked by deleting from database

#### Scenario: Token refresh

- **WHEN** client requests token refresh with valid refresh token
- **THEN** system validates refresh token exists in database
- **AND** validates refresh token is not expired
- **AND** generates new access token
- **AND** generates new refresh token
- **AND** invalidates old refresh token
- **AND** sets new HTTP-only cookies

#### Scenario: Token refresh with invalid token

- **WHEN** client requests refresh with invalid or expired token
- **THEN** system returns 401 Unauthorized
- **AND** clears token cookies

### Requirement: Session Logout

The system SHALL allow users to explicitly terminate their session.

#### Scenario: Successful logout

- **WHEN** authenticated user requests logout
- **THEN** system invalidates refresh token in database
- **AND** clears access token cookie
- **AND** clears refresh token cookie
- **AND** returns 204 No Content

### Requirement: Current User Information

The system SHALL provide endpoint to retrieve current authenticated user information.

#### Scenario: Get current user as Administrator

- **WHEN** authenticated admin requests current user info
- **THEN** system returns user profile (id, username, firstName, lastName, email, role)
- **AND** indicates full system access

#### Scenario: Get current user as Operator

- **WHEN** authenticated operator requests current user info
- **THEN** system returns user profile
- **AND** includes list of assigned point of sales (id, name, code)

#### Scenario: Get current user without authentication

- **WHEN** unauthenticated request is made to current user endpoint
- **THEN** system returns 401 Unauthorized

### Requirement: Login Rate Limiting

The system SHALL protect login endpoint from brute force attacks.

#### Scenario: Rate limit triggered

- **WHEN** more than 5 failed login attempts occur from same IP in 15 minutes
- **THEN** system returns 429 Too Many Requests
- **AND** includes Retry-After header
- **AND** blocks further attempts from that IP

#### Scenario: Successful login resets rate limit

- **WHEN** user successfully logs in
- **THEN** rate limit counter is reset for that IP

