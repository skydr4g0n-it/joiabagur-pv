using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.PointOfSales;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using System.Net;
using System.Net.Http.Json;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for SalesController.
/// Tests sale creation, validation, authorization, stock updates, and transaction integrity.
/// Uses Respawn for database cleanup and Mother Objects for test data creation.
/// </summary>
[Collection(IntegrationTestCollection.Name)]
public class SalesControllerTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;
    private HttpClient? _operatorClient;

    // Test data created via Mother Objects
    private Product _testProduct = null!;
    private PointOfSale _testPos = null!;
    private PaymentMethod _testPaymentMethod = null!;
    private User _testOperator = null!;
    private Inventory _testInventory = null!;

    public SalesControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        // Use Respawn for database cleanup - no manual TRUNCATEs needed
        await _factory.ResetDatabaseAsync();
        
        _adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");
        
        // Create test data using Mother Objects
        await SetupTestDataAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    /// <summary>
    /// Sets up all prerequisite test data using the Mother Object pattern.
    /// Creates interconnected entities needed for sales testing.
    /// </summary>
    private async Task SetupTestDataAsync()
    {
        using var mother = new TestDataMother(_factory.Services);

        // Create Point of Sale
        _testPos = await mother.PointOfSale()
            .WithCode("TEST-POS")
            .WithName("Test Point of Sale")
            .WithAddress("Test Address")
            .WithPhone("600123456")
            .CreateAsync();

        // Use pre-seeded CASH payment method instead of creating a duplicate
        _testPaymentMethod = await mother.Context.PaymentMethods
            .FirstAsync(pm => pm.Code == "CASH");

        // Associate payment method with POS
        mother.Context.PointOfSalePaymentMethods.Add(new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            CreatedAt = DateTime.UtcNow
        });
        await mother.Context.SaveChangesAsync();

        // Create Product
        _testProduct = await mother.Product()
            .WithSku("TEST-SKU-001")
            .WithName("Test Product")
            .WithDescription("Test product for sales")
            .WithPrice(100.00m)
            .CreateAsync();

        // Create Inventory with initial stock
        _testInventory = await mother.Inventory()
            .WithProduct(_testProduct.Id)
            .WithPointOfSale(_testPos.Id)
            .WithQuantity(10)
            .CreateAsync();

        // Create operator and assign to POS
        _testOperator = await mother.User()
            .WithUsername("salesoperator")
            .WithName("Sales", "Operator")
            .AsOperator()
            .AssignedTo(_testPos.Id)
            .CreateAsync();

        // Authenticate as the operator
        _operatorClient = await CreateAuthenticatedClientAsync("salesoperator", "Test123!");
    }

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
            if (cookieParts.Length == 2)
            {
                authClient.DefaultRequestHeaders.Add("Cookie", $"{cookieParts[0]}={cookieParts[1]}");
            }
        }

        return authClient;
    }

    #region Create Sale Tests

    [Fact]
    public async Task CreateSale_ValidRequest_ReturnsCreatedSale()
    {
        // Arrange
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 2,
            Notes = "Test sale"
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        // Verify in database
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var sale = await context.Sales
            .Include(s => s.InventoryMovement)
            .FirstOrDefaultAsync();
        
        sale.Should().NotBeNull();
        sale!.ProductId.Should().Be(_testProduct.Id);
        sale.Quantity.Should().Be(2);
        sale.Price.Should().Be(100.00m);
        sale.InventoryMovement.Should().NotBeNull();
        sale.InventoryMovement!.MovementType.Should().Be(Domain.Enums.MovementType.Sale);
        sale.InventoryMovement.QuantityChange.Should().Be(-2);
    }

    [Fact]
    public async Task CreateSale_InsufficientStock_ReturnsBadRequest()
    {
        // Arrange
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 20, // More than available (10)
            Notes = "Test sale with insufficient stock"
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("insuficiente"); // Spanish error message
    }

    [Fact]
    public async Task CreateSale_InvalidPaymentMethod_ReturnsBadRequest()
    {
        // Arrange
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = Guid.NewGuid(), // Non-existent payment method
            Quantity = 1
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task CreateSale_OperatorNotAssignedToPOS_ReturnsBadRequest()
    {
        // Arrange - Create another POS without assigning operator using Mother Object
        using var mother = new TestDataMother(_factory.Services);
        var otherPos = await mother.PointOfSale()
            .WithCode("OTHER-POS")
            .WithName("Other POS")
            .WithAddress("Other Address")
            .CreateAsync();

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = otherPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("no está asignado");
    }

    [Fact]
    public async Task CreateSale_ZeroQuantity_ReturnsBadRequest()
    {
        // Arrange
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 0
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task CreateSale_UpdatesInventory_Atomically()
    {
        // Arrange
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 3
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        // Verify inventory was updated
        var inventory = await context.Inventories
            .FirstOrDefaultAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
        
        inventory.Should().NotBeNull();
        inventory!.Quantity.Should().Be(7); // 10 - 3

        // Verify movement was created
        var movement = await context.InventoryMovements
            .Where(m => m.InventoryId == inventory.Id && m.MovementType == Domain.Enums.MovementType.Sale)
            .FirstOrDefaultAsync();
        
        movement.Should().NotBeNull();
        movement!.MovementType.Should().Be(Domain.Enums.MovementType.Sale);
        movement.QuantityChange.Should().Be(-3);
        movement.QuantityBefore.Should().Be(10);
        movement.QuantityAfter.Should().Be(7);
    }

    #endregion

    #region Get Sale Tests

    [Fact]
    public async Task GetSaleById_ExistingSale_ReturnsSale()
    {
        // Arrange - Create a sale first
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        };
        var createResponse = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);
        createResponse.EnsureSuccessStatusCode();
        
        // Parse the response to get the sale ID
        using var doc = await System.Text.Json.JsonDocument.ParseAsync(await createResponse.Content.ReadAsStreamAsync());
        var saleId = doc.RootElement.GetProperty("sale").GetProperty("id").GetGuid();

        // Act
        var response = await _operatorClient!.GetAsync($"/api/sales/{saleId}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        
        var sale = await response.Content.ReadFromJsonAsync<SaleDto>();
        sale.Should().NotBeNull();
        sale!.Id.Should().Be((Guid)saleId);
        sale.ProductId.Should().Be(_testProduct.Id);
        sale.Quantity.Should().Be(1);
    }

    [Fact]
    public async Task GetSaleById_NonExistentSale_ReturnsNotFound()
    {
        // Act
        var response = await _operatorClient!.GetAsync($"/api/sales/{Guid.NewGuid()}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    #endregion

    #region Get Sales History Tests

    [Fact]
    public async Task GetSalesHistory_ReturnsOperatorSales()
    {
        // Arrange - Create multiple sales
        for (int i = 0; i < 3; i++)
        {
            var createRequest = new CreateSaleRequest
            {
                ProductId = _testProduct.Id,
                PointOfSaleId = _testPos.Id,
                PaymentMethodId = _testPaymentMethod.Id,
                Quantity = 1
            };
            await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);
        }

        // Act
        var response = await _operatorClient!.GetAsync("/api/sales");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        
        var history = await response.Content.ReadFromJsonAsync<SalesHistoryResponse>();
        history.Should().NotBeNull();
        history!.Sales.Should().HaveCount(3);
        history.TotalCount.Should().Be(3);
    }

    [Fact]
    public async Task GetSalesHistory_WithFilters_ReturnsFilteredResults()
    {
        // Arrange - Create sales
        await _operatorClient!.PostAsJsonAsync("/api/sales", new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        });

        // Act - Filter by product
        var response = await _operatorClient!.GetAsync($"/api/sales?productId={_testProduct.Id}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        
        var history = await response.Content.ReadFromJsonAsync<SalesHistoryResponse>();
        history.Should().NotBeNull();
        history!.Sales.Should().HaveCount(1);
        history.Sales[0].ProductId.Should().Be(_testProduct.Id);
    }

    #endregion

    #region Authorization Tests

    [Fact]
    public async Task CreateSale_Unauthenticated_ReturnsUnauthorized()
    {
        // Arrange
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        };

        // Act
        var response = await _client.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    #endregion

    #region Low Stock Warning Tests

    [Fact]
    public async Task CreateSale_WhenStockBecomesLow_ReturnsLowStockWarning()
    {
        // Arrange - Set inventory to 6 units
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var inventory = await context.Inventories
                .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
            inventory.Quantity = 6;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 2 // After sale, 4 units remain (< 5 threshold)
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("isLowStock");
        content.Should().Contain("\"isLowStock\":true", "low stock warning should be present");
        content.Should().Contain("\"remainingStock\":4", "remaining stock should be 4");
    }

    [Fact]
    public async Task CreateSale_WhenStockAboveThreshold_NoWarning()
    {
        // Arrange - Set inventory to 100 units
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var inventory = await context.Inventories
                .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
            inventory.Quantity = 100;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1 // 99 units remain (well above threshold)
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("\"isLowStock\":false", "no low stock warning should be present");
    }

    [Fact]
    public async Task CreateSale_SellingLastUnit_ReturnsWarning()
    {
        // Arrange - Set inventory to 1 unit
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var inventory = await context.Inventories
                .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
            inventory.Quantity = 1;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1 // Last unit
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("\"isLowStock\":true");
        content.Should().Contain("\"remainingStock\":0");
    }

    #endregion

    #region Concurrent Sales Tests

    [Fact]
    public async Task TwoOperators_SellingLastUnit_OnlyOneShouldSucceed()
    {
        // Arrange - Set inventory to 1 unit
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var inventory = await context.Inventories
                .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
            inventory.Quantity = 1;
            await context.SaveChangesAsync();
        }

        // Create second operator using Mother Object
        using var mother = new TestDataMother(_factory.Services);
        await mother.User()
            .WithUsername("operator2")
            .WithName("Second", "Operator")
            .AsOperator()
            .AssignedTo(_testPos.Id)
            .CreateAsync();

        var operator2Client = await CreateAuthenticatedClientAsync("operator2", "Test123!");

        var request1 = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        };

        var request2 = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        };

        // Act - Simulate concurrent requests
        var task1 = _operatorClient!.PostAsJsonAsync("/api/sales", request1);
        var task2 = operator2Client.PostAsJsonAsync("/api/sales", request2);

        var responses = await Task.WhenAll(task1, task2);

        // Assert
        var successCount = responses.Count(r => r.StatusCode == HttpStatusCode.Created);
        var failureCount = responses.Count(r => r.StatusCode == HttpStatusCode.BadRequest);

        // Exactly one should succeed
        successCount.Should().Be(1, "only one sale should succeed when selling the last unit");
        failureCount.Should().Be(1, "one sale should fail due to insufficient stock");

        // Verify final inventory is 0
        using var finalScope = _factory.Services.CreateScope();
        var finalContext = finalScope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var finalInventory = await finalContext.Inventories
            .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
        
        finalInventory.Quantity.Should().Be(0, "final quantity should be 0 after selling last unit");
    }

    [Fact]
    public async Task MultipleOperators_SellingConcurrently_MaintainDataConsistency()
    {
        // Arrange - Set inventory to 10 units
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var inventory = await context.Inventories
                .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
            inventory.Quantity = 10;
            await context.SaveChangesAsync();
        }

        // Create 10 concurrent requests
        var tasks = new List<Task<HttpResponseMessage>>();
        
        for (int i = 0; i < 10; i++)
        {
            var request = new CreateSaleRequest
            {
                ProductId = _testProduct.Id,
                PointOfSaleId = _testPos.Id,
                PaymentMethodId = _testPaymentMethod.Id,
                Quantity = 1
            };

            tasks.Add(_operatorClient!.PostAsJsonAsync("/api/sales", request));
        }

        // Act
        var responses = await Task.WhenAll(tasks);

        // Assert
        var successCount = responses.Count(r => r.StatusCode == HttpStatusCode.Created);
        
        // All should succeed (or some might fail due to timing, but total sales should be correct)
        successCount.Should().BeGreaterThan(0);

        // Verify final inventory + total sales = 10
        using var finalScope2 = _factory.Services.CreateScope();
        var finalContext2 = finalScope2.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var finalInventory = await finalContext2.Inventories
            .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
        
        var sales = await finalContext2.Sales
            .Where(s => s.ProductId == _testProduct.Id)
            .ToListAsync();
        
        var totalSold = sales.Sum(s => s.Quantity);
        
        // Total sold + remaining inventory should equal starting inventory
        (totalSold + finalInventory.Quantity).Should().Be(10, "inventory consistency must be maintained");
        
        // Inventory should never be negative
        finalInventory.Quantity.Should().BeGreaterThanOrEqualTo(0, "inventory cannot be negative");
    }

    #endregion

    #region Manual Price Edit Tests

    [Fact]
    public async Task CreateSale_WithManualPrice_WhenPosAllows_ShouldUseManualPrice()
    {
        // Arrange - Enable manual price edit on test POS
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var pos = await context.PointOfSales.FirstAsync(p => p.Id == _testPos.Id);
            pos.AllowManualPriceEdit = true;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1,
            Price = 75.00m
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        using var verifyScope = _factory.Services.CreateScope();
        var verifyContext = verifyScope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sale = await verifyContext.Sales.OrderByDescending(s => s.CreatedAt).FirstAsync();
        sale.Price.Should().Be(75.00m);
        sale.PriceWasOverridden.Should().BeTrue();
        sale.OriginalProductPrice.Should().Be(100.00m);
    }

    [Fact]
    public async Task CreateSale_WithManualPrice_WhenPosDisallows_ShouldReturnBadRequest()
    {
        // Arrange - POS has AllowManualPriceEdit = false (default)
        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1,
            Price = 75.00m
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        var content = await response.Content.ReadAsStringAsync();
        content.Should().Contain("Manual price editing is not allowed");
    }

    [Fact]
    public async Task CreateSale_WithoutManualPrice_WhenPosAllows_ShouldUseOfficialPrice()
    {
        // Arrange - Enable manual price edit but don't send price
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var pos = await context.PointOfSales.FirstAsync(p => p.Id == _testPos.Id);
            pos.AllowManualPriceEdit = true;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        using var verifyScope = _factory.Services.CreateScope();
        var verifyContext = verifyScope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sale = await verifyContext.Sales.OrderByDescending(s => s.CreatedAt).FirstAsync();
        sale.Price.Should().Be(100.00m);
        sale.PriceWasOverridden.Should().BeFalse();
        sale.OriginalProductPrice.Should().BeNull();
    }

    [Fact]
    public async Task CreateSale_WithSamePriceAsOfficial_ShouldNotMarkAsOverridden()
    {
        // Arrange
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var pos = await context.PointOfSales.FirstAsync(p => p.Id == _testPos.Id);
            pos.AllowManualPriceEdit = true;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1,
            Price = 100.00m // Same as product price
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        using var verifyScope = _factory.Services.CreateScope();
        var verifyContext = verifyScope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sale = await verifyContext.Sales.OrderByDescending(s => s.CreatedAt).FirstAsync();
        sale.Price.Should().Be(100.00m);
        sale.PriceWasOverridden.Should().BeFalse();
        sale.OriginalProductPrice.Should().BeNull();
    }

    [Fact]
    public async Task GetSaleById_WithOverriddenPrice_ShouldIncludeOverrideFields()
    {
        // Arrange - Create a sale with overridden price
        using (var scope = _factory.Services.CreateScope())
        {
            var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var pos = await context.PointOfSales.FirstAsync(p => p.Id == _testPos.Id);
            pos.AllowManualPriceEdit = true;
            await context.SaveChangesAsync();
        }

        var createRequest = new CreateSaleRequest
        {
            ProductId = _testProduct.Id,
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Quantity = 1,
            Price = 50.00m
        };

        var createResponse = await _operatorClient!.PostAsJsonAsync("/api/sales", createRequest);
        createResponse.EnsureSuccessStatusCode();

        using var doc = await System.Text.Json.JsonDocument.ParseAsync(await createResponse.Content.ReadAsStreamAsync());
        var saleId = doc.RootElement.GetProperty("sale").GetProperty("id").GetGuid();

        // Act
        var response = await _operatorClient!.GetAsync($"/api/sales/{saleId}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var sale = await response.Content.ReadFromJsonAsync<SaleDto>();
        sale.Should().NotBeNull();
        sale!.PriceWasOverridden.Should().BeTrue();
        sale.OriginalProductPrice.Should().Be(100.00m);
        sale.Price.Should().Be(50.00m);
    }

    #endregion

    #region Bulk Sales Tests

    [Fact]
    public async Task CreateBulkSales_ValidRequest_CreatesAllSalesAtomically()
    {
        // Arrange
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 1 },
                new() { ProductId = _testProduct.Id, Quantity = 1 },
                new() { ProductId = _testProduct.Id, Quantity = 1 }
            }
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var result = await response.Content.ReadFromJsonAsync<CreateBulkSalesResult>();
        result.Should().NotBeNull();
        result!.BulkOperationId.Should().NotBeNull().And.NotBe(Guid.Empty);
        result.Sales.Should().HaveCount(3);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sales = await context.Sales
            .Where(s => s.BulkOperationId == result.BulkOperationId)
            .ToListAsync();
        sales.Should().HaveCount(3);

        var inventory = await context.Inventories
            .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
        inventory.Quantity.Should().Be(7); // 10 - 3
    }

    [Fact]
    public async Task CreateBulkSales_InsufficientStock_RollsBackAllLines()
    {
        // Arrange - total 13 > 10 available
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 8 },
                new() { ProductId = _testProduct.Id, Quantity = 5 }
            }
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sales = await context.Sales.ToListAsync();
        sales.Should().BeEmpty("all lines should have been rolled back");

        var inventory = await context.Inventories
            .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
        inventory.Quantity.Should().Be(10, "inventory should remain unchanged after rollback");
    }

    [Fact]
    public async Task CreateBulkSales_EmptyLines_ReturnsBadRequest()
    {
        // Arrange
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>()
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task CreateBulkSales_Unauthenticated_ReturnsUnauthorized()
    {
        // Arrange
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 1 }
            }
        };

        // Act - use a fresh client with no cookies to simulate unauthenticated access
        var unauthClient = _factory.CreateClient(new Microsoft.AspNetCore.Mvc.Testing.WebApplicationFactoryClientOptions
        {
            HandleCookies = false
        });
        var response = await unauthClient.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task CreateBulkSales_OperatorNotAssignedToPOS_ReturnsBadRequest()
    {
        // Arrange - Create another POS without assigning operator
        using var mother = new TestDataMother(_factory.Services);
        var otherPos = await mother.PointOfSale()
            .WithCode("BULK-OTHER-POS")
            .WithName("Other Bulk POS")
            .WithAddress("Other Address")
            .WithPhone("600987654")
            .CreateAsync();

        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = otherPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 1 }
            }
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task CreateBulkSales_GlobalNote_PropagatedToAllSales()
    {
        // Arrange
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Notes = "Bulk sale note",
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 1 },
                new() { ProductId = _testProduct.Id, Quantity = 1 }
            }
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sales = await context.Sales.ToListAsync();
        sales.Should().HaveCount(2);
        sales.Should().AllSatisfy(s => s.Notes.Should().Be("Bulk sale note"));
    }

    [Fact]
    public async Task CreateBulkSales_WithIdempotencyKey_PreventsDuplicate()
    {
        // Arrange
        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 1 },
                new() { ProductId = _testProduct.Id, Quantity = 1 }
            }
        };

        // Act - First request
        var firstMessage = new HttpRequestMessage(HttpMethod.Post, "/api/sales/bulk");
        firstMessage.Content = JsonContent.Create(request);
        firstMessage.Headers.Add("Idempotency-Key", "test-key-123");
        var firstResponse = await _operatorClient!.SendAsync(firstMessage);

        // Act - Second request with same idempotency key
        var secondMessage = new HttpRequestMessage(HttpMethod.Post, "/api/sales/bulk");
        secondMessage.Content = JsonContent.Create(request);
        secondMessage.Headers.Add("Idempotency-Key", "test-key-123");
        var secondResponse = await _operatorClient!.SendAsync(secondMessage);

        // Assert
        firstResponse.StatusCode.Should().Be(HttpStatusCode.Created);
        secondResponse.StatusCode.Should().Be(HttpStatusCode.OK);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var sales = await context.Sales.ToListAsync();
        sales.Should().HaveCount(2, "only the first request should create sales");
    }

    [Fact]
    public async Task CreateBulkSales_WithMultipleProducts_CreatesCorrectInventoryMovements()
    {
        // Arrange - Create a second product with its own inventory
        using var mother = new TestDataMother(_factory.Services);
        var secondProduct = await mother.Product()
            .WithSku("TEST-SKU-002")
            .WithName("Second Product")
            .WithDescription("Second product for bulk sales")
            .WithPrice(50.00m)
            .CreateAsync();

        await mother.Inventory()
            .WithProduct(secondProduct.Id)
            .WithPointOfSale(_testPos.Id)
            .WithQuantity(20)
            .CreateAsync();

        var request = new CreateBulkSalesRequest
        {
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            Lines = new List<BulkSaleLineRequest>
            {
                new() { ProductId = _testProduct.Id, Quantity = 2 },
                new() { ProductId = secondProduct.Id, Quantity = 3 }
            }
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/sales/bulk", request);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);

        var result = await response.Content.ReadFromJsonAsync<CreateBulkSalesResult>();
        result.Should().NotBeNull();
        result!.Sales.Should().HaveCount(2);

        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        var firstInventory = await context.Inventories
            .FirstAsync(i => i.ProductId == _testProduct.Id && i.PointOfSaleId == _testPos.Id);
        firstInventory.Quantity.Should().Be(8); // 10 - 2

        var secondInventory = await context.Inventories
            .FirstAsync(i => i.ProductId == secondProduct.Id && i.PointOfSaleId == _testPos.Id);
        secondInventory.Quantity.Should().Be(17); // 20 - 3

        var sales = await context.Sales
            .Where(s => s.BulkOperationId == result.BulkOperationId)
            .ToListAsync();
        sales.Should().HaveCount(2);
        sales.Select(s => s.BulkOperationId).Distinct().Should().HaveCount(1,
            "all sales should share the same BulkOperationId");
    }

    #endregion
}
