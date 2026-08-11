# API Testing with .http Files

This directory contains HTTP request files for testing the Joiabagur PV API endpoints.

## Prerequisites

- Backend running on `http://localhost:5056`
- VS Code with REST Client extension OR JetBrains Rider/IntelliJ

## Files

- `auth.http` - Authentication endpoints (login, refresh, logout, me)
- `users.http` - User management CRUD operations
- `point-of-sales.http` - Point of sale CRUD and assignments
- `payment-methods.http` - Payment method CRUD operations
- `inventory.http` - Inventory management (assignment, import, adjustment, movements)
- `returns.http` - Returns management (create return, eligible sales, history)
- `ai-search-events.http` - Assisted search telemetry (record a selection; no read routes)

## How to Use

### VS Code with REST Client Extension

1. Install "REST Client" extension by Huachao Mao
2. Open any .http file
3. Click "Send Request" above each request
4. View response in split panel

### JetBrains Rider/IntelliJ

1. Open any .http file
2. Click the ▶️ play button next to each request
3. View response in tool window

### Manual Testing with curl

Example:
```powershell
# Login
curl -X POST http://localhost:5056/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"Admin123!"}' `
  -c cookies.txt

# Get users (with authentication cookie)
curl http://localhost:5056/api/users -b cookies.txt
```

## Testing Workflow

### 1. Start with Authentication
1. Open `auth.http`
2. Run "Login as Admin"
3. Copy token from response if needed
4. Test other auth endpoints

### 2. Create Test Data
1. Create operators in `users.http`
2. Create points of sale in `point-of-sales.http`
3. Assign operators to points of sale

### 3. Configure Payment Methods
1. View predefined payment methods
2. Create custom payment methods if needed
3. Assign payment methods to points of sale

### 4. Test Inventory Management
1. Assign products to a point of sale
2. Download Excel template and create import file
3. Import stock from Excel
4. Adjust stock manually with reasons
5. View movement history
6. Test unassignment (requires 0 stock)

### 5. Test Returns Management
1. Create a sale first (use sales endpoints)
2. Get eligible sales for the product/POS
3. Create return with selected sales
4. Verify return appears in history
5. Check inventory increased by return quantity

### 6. Test Authorization
1. Try accessing admin endpoints without auth → 401
2. Create operator and login as operator
3. Try accessing admin endpoints as operator → 403

## Variables

Replace placeholders in requests:
- `@userId` - Replace with actual user ID from GET response
- `@posId` - Replace with actual point of sale ID
- `@paymentMethodId` - Replace with actual payment method ID

## Tips

- **Authentication**: Cookies are automatically handled by REST Client
- **IDs**: Copy IDs from GET responses to use in other requests
- **Errors**: Check response status and body for error messages
- **Database**: Reset with `docker-compose down -v && docker-compose up -d postgres`

## Default Data

After seed:
- **Admin User**: username=`admin`, password=`Admin123!`
- **Payment Methods**: 6 predefined (CASH, BIZUM, TRANSFER, CARD_OWN, CARD_POS, PAYPAL)

## Alternative: Scalar UI

For interactive testing with a beautiful UI, visit:
**http://localhost:5056/scalar/v1**

Scalar provides:
- Auto-generated API documentation
- Interactive request builder
- Request/response examples
- Schema visualization
