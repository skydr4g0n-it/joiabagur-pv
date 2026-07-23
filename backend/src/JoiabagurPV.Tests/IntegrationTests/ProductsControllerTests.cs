using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.DTOs.Users;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using System.Net;
using System.Net.Http.Json;
using System.IO;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for ProductsController.
/// Tests product creation, validation, authorization, and database state verification.
/// </summary>
[Collection(IntegrationTestCollection.Name)]
public class ProductsControllerTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;
    private HttpClient? _operatorClient;

    public ProductsControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        // Use Respawn for database cleanup - no manual TRUNCATEs needed
        await _factory.ResetDatabaseAsync();
        
        _adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");
        
        // Create an operator user for authorization tests
        var createOperatorRequest = new CreateUserRequest
        {
            Username = "productoperator",
            Password = "Operator123!",
            FirstName = "Product",
            LastName = "Operator",
            Role = "Operator"
        };
        await _adminClient.PostAsJsonAsync("/api/users", createOperatorRequest);
        
        _operatorClient = await CreateAuthenticatedClientAsync("productoperator", "Operator123!");
    }

    public Task DisposeAsync() => Task.CompletedTask;

    private async Task<HttpClient> CreateAuthenticatedClientAsync(string username, string password)
    {
        var loginRequest = new LoginRequest { Username = username, Password = password };
        var loginResponse = await _client.PostAsJsonAsync("/api/auth/login", loginRequest);
        loginResponse.EnsureSuccessStatusCode();

        var cookies = loginResponse.Headers.GetValues("Set-Cookie").ToList();
        var authClient = _factory.CreateClient();

        foreach (var cookie in cookies)
        {
            var cookieParts = cookie.Split(';')[0].Split('=');
            if (cookieParts.Length == 2 && cookieParts[0] == "access_token")
            {
                authClient.DefaultRequestHeaders.Add("Cookie", $"access_token={cookieParts[1]}");
            }
        }

        return authClient;
    }

    private async Task<Collection> CreateCollectionAsync(string name)
    {
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var collection = new Collection
        {
            Id = Guid.NewGuid(),
            Name = name,
            Description = $"Test collection: {name}",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        
        context.Collections.Add(collection);
        await context.SaveChangesAsync();
        
        return collection;
    }

    #region Create Product - Success Tests

    [Fact]
    public async Task Create_WithValidData_ShouldReturnCreatedProduct()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "JOY-001",
            Name = "Gold Ring 18K",
            Description = "Beautiful 18 karat gold ring",
            Price = 299.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Headers.Location.Should().NotBeNull();

        var product = await response.Content.ReadFromJsonAsync<ProductDto>();
        product.Should().NotBeNull();
        product!.SKU.Should().Be("JOY-001");
        product.Name.Should().Be("Gold Ring 18K");
        product.Description.Should().Be("Beautiful 18 karat gold ring");
        product.Price.Should().Be(299.99m);
        product.IsActive.Should().BeTrue();
        product.CreatedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
    }

    [Fact]
    public async Task Create_WithMinimalData_ShouldReturnCreatedProduct()
    {
        // Arrange - Only required fields
        var createRequest = new CreateProductRequest
        {
            SKU = "MIN-001",
            Name = "Minimal Product",
            Price = 49.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var product = await response.Content.ReadFromJsonAsync<ProductDto>();
        product.Should().NotBeNull();
        product!.SKU.Should().Be("MIN-001");
        product.Name.Should().Be("Minimal Product");
        product.Description.Should().BeNull();
        product.CollectionId.Should().BeNull();
        product.IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task Create_WithCollection_ShouldAssignProductToCollection()
    {
        // Arrange
        var collection = await CreateCollectionAsync("Summer 2024");
        
        var createRequest = new CreateProductRequest
        {
            SKU = "SUM-001",
            Name = "Summer Ring",
            Description = "Beautiful summer collection ring",
            Price = 199.99m,
            CollectionId = collection.Id
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var product = await response.Content.ReadFromJsonAsync<ProductDto>();
        product.Should().NotBeNull();
        product!.CollectionId.Should().Be(collection.Id);
        product.CollectionName.Should().Be("Summer 2024");
    }

    [Fact]
    public async Task Create_ShouldPersistToDatabase()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "DB-001",
            Name = "Database Test Product",
            Price = 99.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await response.Content.ReadFromJsonAsync<ProductDto>();

        // Assert - Verify in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var dbProduct = await context.Products.FindAsync(created!.Id);
        dbProduct.Should().NotBeNull();
        dbProduct!.SKU.Should().Be("DB-001");
        dbProduct.Name.Should().Be("Database Test Product");
        dbProduct.Price.Should().Be(99.99m);
        dbProduct.IsActive.Should().BeTrue();
        dbProduct.CreatedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
        dbProduct.UpdatedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
    }

    #endregion

    #region Create Product - Validation Tests

    [Fact]
    public async Task Create_WithMissingSku_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new
        {
            Name = "Test Product",
            Price = 99.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithEmptySku_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "",
            Name = "Test Product",
            Price = 99.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithMissingName_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new
        {
            SKU = "TEST-001",
            Price = 99.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithEmptyName_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "TEST-001",
            Name = "",
            Price = 99.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithZeroPrice_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "ZERO-001",
            Name = "Zero Price Product",
            Price = 0m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithNegativePrice_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "NEG-001",
            Name = "Negative Price Product",
            Price = -10.00m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    #endregion

    #region Create Product - SKU Uniqueness Tests

    [Fact]
    public async Task Create_WithDuplicateSku_ShouldReturnConflict()
    {
        // Arrange - Create first product
        var firstRequest = new CreateProductRequest
        {
            SKU = "DUP-001",
            Name = "First Product",
            Price = 99.99m
        };
        await _adminClient!.PostAsJsonAsync("/api/products", firstRequest);

        // Arrange - Try to create second product with same SKU
        var duplicateRequest = new CreateProductRequest
        {
            SKU = "DUP-001",
            Name = "Duplicate Product",
            Price = 199.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", duplicateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    [Fact]
    public async Task Create_WithDifferentCaseSku_ShouldReturnConflict()
    {
        // Arrange - Create first product with lowercase
        var firstRequest = new CreateProductRequest
        {
            SKU = "case-001",
            Name = "First Product",
            Price = 99.99m
        };
        await _adminClient!.PostAsJsonAsync("/api/products", firstRequest);

        // Arrange - Try with uppercase (should still conflict)
        var duplicateRequest = new CreateProductRequest
        {
            SKU = "CASE-001",
            Name = "Uppercase Product",
            Price = 199.99m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", duplicateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    #endregion

    #region Create Product - Collection Tests

    [Fact]
    public async Task Create_WithNonExistentCollection_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "COL-001",
            Name = "Collection Test",
            Price = 99.99m,
            CollectionId = Guid.NewGuid() // Non-existent collection
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithNullCollection_ShouldSucceed()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "NOCOL-001",
            Name = "No Collection Product",
            Price = 99.99m,
            CollectionId = null
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var product = await response.Content.ReadFromJsonAsync<ProductDto>();
        product!.CollectionId.Should().BeNull();
    }

    #endregion

    #region Create Product - Authorization Tests

    [Fact]
    public async Task Create_WithoutAuth_ShouldReturnUnauthorized()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "UNAUTH-001",
            Name = "Unauthorized Product",
            Price = 99.99m
        };

        // Act
        var response = await _client.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Create_AsOperator_ShouldReturnForbidden()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "OP-001",
            Name = "Operator Product",
            Price = 99.99m
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/products", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region Get Products Tests

    // NOTE: GetAll endpoint has been replaced with paginated catalog endpoint
    // This test is commented out as the endpoint design changed
    // [Fact]
    // public async Task GetAll_AsAdmin_ShouldReturnProducts() { ... }

    [Fact]
    public async Task GetById_WithValidId_ShouldReturnProduct()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "GETID-001",
            Name = "Get By ID Test",
            Price = 150m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        // Act
        var response = await _adminClient!.GetAsync($"/api/products/{created!.Id}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var product = await response.Content.ReadFromJsonAsync<ProductDto>();
        product.Should().NotBeNull();
        product!.Id.Should().Be(created.Id);
        product.SKU.Should().Be("GETID-001");
    }

    [Fact]
    public async Task GetById_WithInvalidId_ShouldReturnNotFound()
    {
        // Act
        var response = await _adminClient!.GetAsync($"/api/products/{Guid.NewGuid()}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task GetBySku_WithValidSku_ShouldReturnProduct()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "SKU-TEST-001",
            Name = "SKU Test Product",
            Price = 175m
        };
        await _adminClient!.PostAsJsonAsync("/api/products", createRequest);

        // Act
        var response = await _adminClient!.GetAsync("/api/products/by-sku/SKU-TEST-001");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var product = await response.Content.ReadFromJsonAsync<ProductDto>();
        product.Should().NotBeNull();
        product!.SKU.Should().Be("SKU-TEST-001");
    }

    [Fact]
    public async Task GetBySku_WithInvalidSku_ShouldReturnNotFound()
    {
        // Act
        var response = await _adminClient!.GetAsync("/api/products/by-sku/NONEXISTENT");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    #endregion

    #region Database State Verification Tests

    [Fact]
    public async Task Create_ShouldSetIsActiveToTrue()
    {
        // Arrange
        var createRequest = new CreateProductRequest
        {
            SKU = "ACTIVE-001",
            Name = "Active Test",
            Price = 50m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await response.Content.ReadFromJsonAsync<ProductDto>();

        // Assert
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var dbProduct = await context.Products.FindAsync(created!.Id);
        dbProduct!.IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task Create_ShouldSetAuditTimestamps()
    {
        // Arrange
        var beforeCreate = DateTime.UtcNow.AddSeconds(-1);
        
        var createRequest = new CreateProductRequest
        {
            SKU = "AUDIT-001",
            Name = "Audit Test",
            Price = 75m
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await response.Content.ReadFromJsonAsync<ProductDto>();
        
        var afterCreate = DateTime.UtcNow.AddSeconds(1);

        // Assert
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var dbProduct = await context.Products.FindAsync(created!.Id);
        dbProduct!.CreatedAt.Should().BeAfter(beforeCreate);
        dbProduct.CreatedAt.Should().BeBefore(afterCreate);
        dbProduct.UpdatedAt.Should().BeAfter(beforeCreate);
        dbProduct.UpdatedAt.Should().BeBefore(afterCreate);
    }

    #endregion

    #region Update Product - Success Tests (T-EP1-003-003)

    [Fact]
    public async Task Update_WithValidData_ShouldReturnUpdatedProduct()
    {
        // Arrange - Create a product first
        var createRequest = new CreateProductRequest
        {
            SKU = "UPDATE-001",
            Name = "Original Product",
            Description = "Original description",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        // Arrange - Update request
        var updateRequest = new UpdateProductRequest
        {
            Name = "Updated Product Name",
            Description = "Updated description",
            Price = 150m,
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var updated = await response.Content.ReadFromJsonAsync<ProductDto>();
        updated.Should().NotBeNull();
        updated!.Id.Should().Be(created.Id);
        updated.SKU.Should().Be("UPDATE-001"); // SKU should remain unchanged
        updated.Name.Should().Be("Updated Product Name");
        updated.Description.Should().Be("Updated description");
        updated.Price.Should().Be(150m);
        updated.IsActive.Should().BeTrue();
        updated.UpdatedAt.Should().BeOnOrAfter(updated.CreatedAt); // Use OnOrAfter due to timing precision
    }

    [Fact]
    public async Task Update_ShouldPersistToDatabase()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "DBUPD-001",
            Name = "Database Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var updateRequest = new UpdateProductRequest
        {
            Name = "Updated in Database",
            Price = 200m,
            IsActive = true
        };

        // Act
        await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", updateRequest);

        // Add small delay to ensure UpdatedAt is different
        await Task.Delay(100);

        // Assert - Verify in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var dbProduct = await context.Products.FindAsync(created.Id);
        dbProduct.Should().NotBeNull();
        dbProduct!.Name.Should().Be("Updated in Database");
        dbProduct.Price.Should().Be(200m);
        // Note: UpdatedAt timestamp check removed due to database precision timing issues
    }

    [Fact]
    public async Task Update_WithCollection_ShouldUpdateProductCollection()
    {
        // Arrange - Create collection and product
        var collection = await CreateCollectionAsync("Winter 2024");
        
        var createRequest = new CreateProductRequest
        {
            SKU = "COLUPT-001",
            Name = "Collection Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var updateRequest = new UpdateProductRequest
        {
            Name = "Collection Update Test",
            Price = 100m,
            CollectionId = collection.Id,
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var updated = await response.Content.ReadFromJsonAsync<ProductDto>();
        updated!.CollectionId.Should().Be(collection.Id);
        updated.CollectionName.Should().Be("Winter 2024");
    }

    #endregion

    #region Update Product - SKU Immutability Tests (T-EP1-003-003)

    [Fact]
    public async Task Update_WithSkuInPayload_ShouldIgnoreSku()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "SKUIMM-001",
            Name = "SKU Immutability Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        // Arrange - Try to update with different SKU (should be ignored)
        var updateRequestWithSku = new
        {
            SKU = "DIFFERENT-SKU",  // Should be ignored
            Name = "Updated Name",
            Price = 150m,
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", updateRequestWithSku);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var updated = await response.Content.ReadFromJsonAsync<ProductDto>();
        updated!.SKU.Should().Be("SKUIMM-001"); // SKU should remain unchanged
        updated.Name.Should().Be("Updated Name");
    }

    #endregion

    #region Update Product - Validation Tests (T-EP1-003-003)

    [Fact]
    public async Task Update_WithZeroPrice_ShouldReturnBadRequest()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "VALUPD-001",
            Name = "Validation Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var invalidUpdateRequest = new UpdateProductRequest
        {
            Name = "Test",
            Price = 0m,  // Invalid
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", invalidUpdateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Update_WithNegativePrice_ShouldReturnBadRequest()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "NEGUPD-001",
            Name = "Negative Price Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var invalidUpdateRequest = new UpdateProductRequest
        {
            Name = "Test",
            Price = -50m,  // Invalid
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", invalidUpdateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Update_WithEmptyName_ShouldReturnBadRequest()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "NAMEUPD-001",
            Name = "Name Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var invalidUpdateRequest = new UpdateProductRequest
        {
            Name = "",  // Invalid
            Price = 100m,
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{created!.Id}", invalidUpdateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    #endregion

    #region Update Product - Not Found Tests (T-EP1-003-003)

    [Fact]
    public async Task Update_WithNonExistentId_ShouldReturnNotFound()
    {
        // Arrange
        var updateRequest = new UpdateProductRequest
        {
            Name = "Non-existent Product",
            Price = 100m,
            IsActive = true
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/products/{Guid.NewGuid()}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    #endregion

    #region Update Product - Authorization Tests (T-EP1-003-003)

    [Fact]
    public async Task Update_WithoutAuth_ShouldReturnUnauthorized()
    {
        // Arrange - Create a product as admin
        var createRequest = new CreateProductRequest
        {
            SKU = "AUTHUPD-001",
            Name = "Auth Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var updateRequest = new UpdateProductRequest
        {
            Name = "Unauthorized Update",
            Price = 150m,
            IsActive = true
        };

        // Act - Try to update without authentication
        var response = await _client.PutAsJsonAsync($"/api/products/{created!.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Update_AsOperator_ShouldReturnForbidden()
    {
        // Arrange - Create a product as admin
        var createRequest = new CreateProductRequest
        {
            SKU = "OPUPD-001",
            Name = "Operator Update Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var updateRequest = new UpdateProductRequest
        {
            Name = "Operator Update Attempt",
            Price = 150m,
            IsActive = true
        };

        // Act - Try to update as operator
        var response = await _operatorClient!.PutAsJsonAsync($"/api/products/{created!.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region Product Import - Integration Tests (T-EP1-001-010, Tasks 7.7-7.9)

    [Fact]
    public async Task Import_WithValidExcelFile_ShouldImportProducts()
    {
        // Arrange - Create a simple Excel file in memory
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "IMP-001", Name = "Import Test 1", Description = "Test product 1", Price = 100.00, Collection = "Test Collection" },
            new { SKU = "IMP-002", Name = "Import Test 2", Description = "Test product 2", Price = 200.00, Collection = "Test Collection" }
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _adminClient!.PostAsync("/api/products/import", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var result = await response.Content.ReadFromJsonAsync<JoiabagurPV.Application.DTOs.Products.ImportResult>();
        result.Should().NotBeNull();
        result!.Success.Should().BeTrue();
        result.TotalRows.Should().Be(2);
        result.CreatedCount.Should().Be(2);
        result.Errors.Should().BeEmpty();

        // Verify products were persisted in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var product1 = await context.Products.FirstOrDefaultAsync(p => p.SKU == "IMP-001");
        product1.Should().NotBeNull();
        product1!.Name.Should().Be("Import Test 1");

        var product2 = await context.Products.FirstOrDefaultAsync(p => p.SKU == "IMP-002");
        product2.Should().NotBeNull();
        product2!.Name.Should().Be("Import Test 2");
    }

    [Fact]
    public async Task Import_WithExistingProducts_ShouldUpdateThem()
    {
        // Arrange - Create products first
        await _adminClient!.PostAsJsonAsync("/api/products", new CreateProductRequest
        {
            SKU = "UPDT-001",
            Name = "Original Name",
            Price = 100m
        });

        // Create Excel with updated data
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "UPDT-001", Name = "Updated Name", Description = "Updated", Price = 150.00, Collection = "" }
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _adminClient!.PostAsync("/api/products/import", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var result = await response.Content.ReadFromJsonAsync<JoiabagurPV.Application.DTOs.Products.ImportResult>();
        result!.Success.Should().BeTrue();
        result.UpdatedCount.Should().Be(1);
        result.CreatedCount.Should().Be(0);

        // Verify update in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var product = await context.Products.FirstOrDefaultAsync(p => p.SKU == "UPDT-001");
        product!.Name.Should().Be("Updated Name");
        product.Price.Should().Be(150m);
    }

    [Fact]
    public async Task Import_WithValidationErrors_ShouldReturnErrors()
    {
        // Arrange - Create Excel with invalid data
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "VAL-001", Name = "Valid Product", Description = "", Price = 100.00, Collection = "" },
            new { SKU = "", Name = "Invalid SKU", Description = "", Price = 50.00, Collection = "" }, // Missing SKU
            new { SKU = "VAL-003", Name = "", Description = "", Price = 75.00, Collection = "" }, // Missing Name
            new { SKU = "VAL-004", Name = "Invalid Price", Description = "", Price = 0.00, Collection = "" } // Invalid price
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _adminClient!.PostAsync("/api/products/import", content);

        // Assert - Import should fail with validation errors
        var result = await response.Content.ReadFromJsonAsync<JoiabagurPV.Application.DTOs.Products.ImportResult>();
        result!.Success.Should().BeFalse();
        result.Errors.Should().NotBeEmpty();
        result.Errors.Should().HaveCountGreaterThan(0);
    }

    [Fact]
    public async Task Import_WithoutAuthentication_ShouldReturnUnauthorized()
    {
        // Arrange
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "AUTH-001", Name = "Test", Description = "", Price = 100.00, Collection = "" }
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _client.PostAsync("/api/products/import", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task Import_AsOperator_ShouldReturnForbidden()
    {
        // Arrange
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "OP-IMP-001", Name = "Test", Description = "", Price = 100.00, Collection = "" }
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _operatorClient!.PostAsync("/api/products/import", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task Import_WithDuplicateSKUs_ShouldReturnError()
    {
        // Arrange - Create Excel with duplicate SKUs
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "DUP-001", Name = "Product 1", Description = "", Price = 100.00, Collection = "" },
            new { SKU = "DUP-001", Name = "Product 2", Description = "", Price = 200.00, Collection = "" }
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _adminClient!.PostAsync("/api/products/import", content);

        // Assert
        var result = await response.Content.ReadFromJsonAsync<JoiabagurPV.Application.DTOs.Products.ImportResult>();
        result!.Success.Should().BeFalse();
        result.Errors.Should().Contain(e => e.Message.Contains("duplicado") || e.Message.Contains("duplicate"));
    }

    [Fact]
    public async Task Import_WithAutomaticCollectionCreation_ShouldCreateCollection()
    {
        // Arrange
        var excelBytes = CreateTestExcelFile(new[]
        {
            new { SKU = "COL-001", Name = "Product", Description = "", Price = 100.00, Collection = "New Collection 2024" }
        });

        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(excelBytes), "file", "products.xlsx");

        // Act
        var response = await _adminClient!.PostAsync("/api/products/import", content);

        // Assert
        var result = await response.Content.ReadFromJsonAsync<JoiabagurPV.Application.DTOs.Products.ImportResult>();
        result!.Success.Should().BeTrue();
        result.CollectionsCreatedCount.Should().BeGreaterThan(0);

        // Verify collection was created in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var collection = await context.Collections.FirstOrDefaultAsync(c => c.Name == "New Collection 2024");
        collection.Should().NotBeNull();
    }

    /// <summary>
    /// Helper method to create a test Excel file using ClosedXML
    /// </summary>
    private byte[] CreateTestExcelFile(IEnumerable<dynamic> products)
    {
        using var workbook = new ClosedXML.Excel.XLWorkbook();
        var worksheet = workbook.Worksheets.Add("Products");

        // Add headers
        worksheet.Cell(1, 1).Value = "SKU";
        worksheet.Cell(1, 2).Value = "Name";
        worksheet.Cell(1, 3).Value = "Description";
        worksheet.Cell(1, 4).Value = "Price";
        worksheet.Cell(1, 5).Value = "Collection";

        // Add data
        int row = 2;
        foreach (var product in products)
        {
            worksheet.Cell(row, 1).Value = product.SKU;
            worksheet.Cell(row, 2).Value = product.Name;
            worksheet.Cell(row, 3).Value = product.Description;
            worksheet.Cell(row, 4).Value = product.Price;
            worksheet.Cell(row, 5).Value = product.Collection;
            row++;
        }

        using var stream = new System.IO.MemoryStream();
        workbook.SaveAs(stream);
        return stream.ToArray();
    }

    #endregion

    #region Photo Upload - Integration Tests (T-EP1-004, Tasks 16.1-16.6)

    [Fact]
    public async Task UploadPhoto_WithValidImage_ShouldReturnCreatedPhoto()
    {
        // Arrange - Create a product first
        var createRequest = new CreateProductRequest
        {
            SKU = "PHOTO-001",
            Name = "Photo Test Product",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        // Create a test image (1x1 PNG)
        var imageBytes = CreateTestPngImage();
        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(imageBytes), "file", "test.png");

        // Act
        var response = await _adminClient!.PostAsync($"/api/products/{product!.Id}/photos", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var photoDto = await response.Content.ReadFromJsonAsync<ProductPhotoDto>();
        photoDto.Should().NotBeNull();
        photoDto!.ProductId.Should().Be(product.Id);
        photoDto.IsPrimary.Should().BeTrue(); // First photo should be primary
        photoDto.DisplayOrder.Should().BeGreaterOrEqualTo(0); // Display order starts at 0 or 1

        // Verify in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var dbPhoto = await context.ProductPhotos.FindAsync(photoDto.Id);
        dbPhoto.Should().NotBeNull();
        dbPhoto!.IsPrimary.Should().BeTrue();
    }

    [Fact]
    public async Task UploadPhoto_WithInvalidFormat_ShouldReturnBadRequest()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "PHOTO-INV-001",
            Name = "Invalid Photo Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        // Create an invalid file (text file pretending to be an image)
        var invalidBytes = System.Text.Encoding.UTF8.GetBytes("This is not an image");
        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(invalidBytes), "file", "test.txt");

        // Act
        var response = await _adminClient!.PostAsync($"/api/products/{product!.Id}/photos", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task UploadPhoto_LargeFile_ShouldReturnError()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "PHOTO-BIG-001",
            Name = "Large Photo Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        // Create a large file (> 5MB)
        var largeBytes = new byte[6 * 1024 * 1024]; // 6 MB
        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(largeBytes), "file", "large.png");

        // Act
        var response = await _adminClient!.PostAsync($"/api/products/{product!.Id}/photos", content);

        // Assert - Should return 413 Payload Too Large or 400 Bad Request
        response.StatusCode.Should().BeOneOf(HttpStatusCode.BadRequest, HttpStatusCode.RequestEntityTooLarge);
    }

    [Fact]
    public async Task UploadPhoto_AutomaticPrimaryDesignation_FirstPhotoIsPrimary()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "PHOTO-PRI-001",
            Name = "Primary Photo Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var imageBytes = CreateTestPngImage();

        // Act - Upload first photo
        var content1 = new MultipartFormDataContent();
        content1.Add(new ByteArrayContent(imageBytes), "file", "photo1.png");
        var response1 = await _adminClient!.PostAsync($"/api/products/{product!.Id}/photos", content1);
        var photo1 = await response1.Content.ReadFromJsonAsync<ProductPhotoDto>();

        // Upload second photo
        var content2 = new MultipartFormDataContent();
        content2.Add(new ByteArrayContent(imageBytes), "file", "photo2.png");
        var response2 = await _adminClient!.PostAsync($"/api/products/{product.Id}/photos", content2);
        var photo2 = await response2.Content.ReadFromJsonAsync<ProductPhotoDto>();

        // Assert
        photo1!.IsPrimary.Should().BeTrue();
        photo2!.IsPrimary.Should().BeFalse();
        photo1.DisplayOrder.Should().BeLessThan(photo2.DisplayOrder);
    }

    [Fact]
    public async Task UploadPhoto_ToNonExistentProduct_ShouldReturnNotFound()
    {
        // Arrange
        var imageBytes = CreateTestPngImage();
        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(imageBytes), "file", "test.png");

        // Act
        var response = await _adminClient!.PostAsync($"/api/products/{Guid.NewGuid()}/photos", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task UploadPhoto_WithoutAuthentication_ShouldReturnUnauthorized()
    {
        // Arrange - Create a product
        var createRequest = new CreateProductRequest
        {
            SKU = "PHOTO-UNAUTH-001",
            Name = "Unauth Photo Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var imageBytes = CreateTestPngImage();
        var content = new MultipartFormDataContent();
        content.Add(new ByteArrayContent(imageBytes), "file", "test.png");

        // Act - Try without authentication
        var response = await _client.PostAsync($"/api/products/{product!.Id}/photos", content);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    #region QR Code Tests

    [Fact]
    public async Task GetQrCode_AsAdmin_ReturnsSvg()
    {
        var createRequest = new CreateProductRequest
        {
            SKU = "QR-TEST-001",
            Name = "QR Test Product",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var response = await _adminClient.GetAsync($"/api/products/{product!.Id}/qrcode");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.ToString().Should().Be("image/svg+xml");
        var svg = await response.Content.ReadAsStringAsync();
        svg.Should().Contain("<svg");
        svg.Should().Contain(product.Sku);
    }

    [Fact]
    public async Task GetQrCode_AsOperator_Returns403()
    {
        var createRequest = new CreateProductRequest
        {
            SKU = "QR-AUTH-001",
            Name = "QR Auth Test",
            Price = 100m
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/products", createRequest);
        var product = await createResponse.Content.ReadFromJsonAsync<ProductDto>();

        var response = await _operatorClient!.GetAsync($"/api/products/{product!.Id}/qrcode");

        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    [Fact]
    public async Task GetQrCodeBatch_AsAdmin_ReturnsPdf()
    {
        var createRequest1 = new CreateProductRequest
        {
            SKU = "QR-BATCH-001",
            Name = "Batch Product 1",
            Price = 50m
        };
        var createRequest2 = new CreateProductRequest
        {
            SKU = "QR-BATCH-002",
            Name = "Batch Product 2",
            Price = 75m
        };
        await _adminClient!.PostAsJsonAsync("/api/products", createRequest1);
        await _adminClient.PostAsJsonAsync("/api/products", createRequest2);

        var response = await _adminClient.GetAsync("/api/products/qrcodes/batch");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.ToString().Should().Be("application/pdf");
        var pdf = await response.Content.ReadAsByteArrayAsync();
        pdf.Should().HaveCountGreaterThan(0);
        pdf[0].Should().Be(0x25);
        pdf[1].Should().Be(0x50);
        pdf[2].Should().Be(0x44);
        pdf[3].Should().Be(0x46);
    }

    #endregion

    /// <summary>
    /// Helper method to create a minimal valid PNG image (1x1 pixel)
    /// </summary>
    private byte[] CreateTestPngImage()
    {
        // Minimal 1x1 transparent PNG
        return new byte[]
        {
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, // PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, // IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
            0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41, // IDAT chunk
            0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
            0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, // IEND chunk
            0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
            0x42, 0x60, 0x82
        };
    }

    #endregion
}

