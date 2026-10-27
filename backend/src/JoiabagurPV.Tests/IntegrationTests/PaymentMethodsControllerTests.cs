using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.PaymentMethods;
using JoiabagurPV.Application.DTOs.Users;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using Microsoft.Extensions.DependencyInjection;
using System.Net;
using System.Net.Http.Json;

namespace JoiabagurPV.Tests.IntegrationTests;

/// <summary>
/// Integration tests for PaymentMethodsController.
/// Tests all CRUD operations, authorization, and validation scenarios.
/// </summary>
[Collection(IntegrationTestCollection.Name)]
public class PaymentMethodsControllerTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;
    private HttpClient? _operatorClient;

    public PaymentMethodsControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        _adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");
        
        // Create an operator user for authorization tests
        var createOperatorRequest = new CreateUserRequest
        {
            Username = "testoperator",
            Password = "Operator123!",
            FirstName = "Test",
            LastName = "Operator",
            Role = "Operator"
        };
        await _adminClient.PostAsJsonAsync("/api/users", createOperatorRequest);
        
        _operatorClient = await CreateAuthenticatedClientAsync("testoperator", "Operator123!");
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

    #region GetAll Tests

    [Fact]
    public async Task GetAll_AsAdmin_ShouldReturnPredefinedPaymentMethods()
    {
        // Act - Seed data should create 6 predefined payment methods
        var response = await _adminClient!.GetAsync("/api/payment-methods");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var paymentMethods = await response.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        paymentMethods.Should().NotBeNull();
        paymentMethods.Should().HaveCountGreaterThanOrEqualTo(6); // CASH, BIZUM, TRANSFER, CARD_OWN, CARD_POS, PAYPAL
        
        // Verify predefined methods exist
        paymentMethods.Should().Contain(pm => pm.Code == "CASH");
        paymentMethods.Should().Contain(pm => pm.Code == "BIZUM");
        paymentMethods.Should().Contain(pm => pm.Code == "TRANSFER");
        paymentMethods.Should().Contain(pm => pm.Code == "CARD_OWN");
        paymentMethods.Should().Contain(pm => pm.Code == "CARD_POS");
        paymentMethods.Should().Contain(pm => pm.Code == "PAYPAL");
    }

    [Fact]
    public async Task GetAll_WithIncludeInactive_ShouldReturnAllPaymentMethods()
    {
        // Arrange - Create and deactivate a payment method
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "TEST_PM",
            Name = "Test Payment",
            Description = "Test payment method"
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<PaymentMethodDto>();

        await _adminClient!.PatchAsJsonAsync(
            $"/api/payment-methods/{created!.Id}/status",
            new { IsActive = false }
        );

        // Act - Get all including inactive
        var response = await _adminClient!.GetAsync("/api/payment-methods?includeInactive=true");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var paymentMethods = await response.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        paymentMethods.Should().Contain(pm => pm.Code == "TEST_PM" && !pm.IsActive);
    }

    [Fact]
    public async Task GetAll_WithoutAuth_ShouldReturnUnauthorized()
    {
        // Act
        var response = await _client.GetAsync("/api/payment-methods");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }

    [Fact]
    public async Task GetAll_AsOperator_ShouldReturnForbidden()
    {
        // Act
        var response = await _operatorClient!.GetAsync("/api/payment-methods");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region GetById Tests

    [Fact]
    public async Task GetById_WithValidId_ShouldReturnPaymentMethod()
    {
        // Arrange - Get an existing payment method from seed data
        var allResponse = await _adminClient!.GetAsync("/api/payment-methods");
        var allMethods = await allResponse.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        var existingMethod = allMethods!.First(pm => pm.Code == "CASH");

        // Act
        var response = await _adminClient!.GetAsync($"/api/payment-methods/{existingMethod.Id}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var paymentMethod = await response.Content.ReadFromJsonAsync<PaymentMethodDto>();
        paymentMethod.Should().NotBeNull();
        paymentMethod!.Id.Should().Be(existingMethod.Id);
        paymentMethod.Code.Should().Be("CASH");
    }

    [Fact]
    public async Task GetById_WithInvalidId_ShouldReturnNotFound()
    {
        // Act
        var response = await _adminClient!.GetAsync($"/api/payment-methods/{Guid.NewGuid()}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task GetById_AsOperator_ShouldReturnForbidden()
    {
        // Act
        var response = await _operatorClient!.GetAsync($"/api/payment-methods/{Guid.NewGuid()}");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region Create Tests

    [Fact]
    public async Task Create_WithValidData_ShouldReturnCreatedPaymentMethod()
    {
        // Arrange
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "NEW_METHOD",
            Name = "New Payment Method",
            Description = "A new payment method for testing"
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Created);
        response.Headers.Location.Should().NotBeNull();

        var paymentMethod = await response.Content.ReadFromJsonAsync<PaymentMethodDto>();
        paymentMethod.Should().NotBeNull();
        paymentMethod!.Code.Should().Be("NEW_METHOD");
        paymentMethod.Name.Should().Be("New Payment Method");
        paymentMethod.Description.Should().Be("A new payment method for testing");
        paymentMethod.IsActive.Should().BeTrue();
        paymentMethod.CreatedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
    }

    [Fact]
    public async Task Create_WithDuplicateCode_ShouldReturnConflict()
    {
        // Arrange - CASH already exists from seed data
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "CASH",
            Name = "Duplicate Cash",
            Description = "This should fail"
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }

    [Fact]
    public async Task Create_WithMissingCode_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "", // Empty code
            Name = "Test Payment",
            Description = "Test"
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithMissingName_ShouldReturnBadRequest()
    {
        // Arrange
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "TEST_CODE",
            Name = "", // Empty name
            Description = "Test"
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_WithInvalidCodeFormat_ShouldReturnBadRequest()
    {
        // Arrange - Code must be uppercase alphanumeric with underscores
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "invalid-code", // Lowercase with hyphens (should be uppercase with underscores)
            Name = "Test Payment",
            Description = "Test"
        };

        // Act
        var response = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Create_AsOperator_ShouldReturnForbidden()
    {
        // Arrange
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "OP_TEST",
            Name = "Operator Test",
            Description = "Should be forbidden"
        };

        // Act
        var response = await _operatorClient!.PostAsJsonAsync("/api/payment-methods", createRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region Update Tests

    [Fact]
    public async Task Update_WithValidData_ShouldReturnUpdatedPaymentMethod()
    {
        // Arrange - Create a payment method first
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "UPDATE_TEST",
            Name = "Original Name",
            Description = "Original Description"
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<PaymentMethodDto>();

        var updateRequest = new UpdatePaymentMethodRequest
        {
            Name = "Updated Name",
            Description = "Updated Description"
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/payment-methods/{created!.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var updated = await response.Content.ReadFromJsonAsync<PaymentMethodDto>();
        updated.Should().NotBeNull();
        updated!.Id.Should().Be(created.Id);
        updated.Code.Should().Be("UPDATE_TEST"); // Code should remain unchanged
        updated.Name.Should().Be("Updated Name");
        updated.Description.Should().Be("Updated Description");
        updated.UpdatedAt.Should().BeAfter(created.CreatedAt);
    }

    [Fact]
    public async Task Update_WithNonExistentId_ShouldReturnNotFound()
    {
        // Arrange
        var updateRequest = new UpdatePaymentMethodRequest
        {
            Name = "Updated Name",
            Description = "Updated Description"
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/payment-methods/{Guid.NewGuid()}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task Update_WithMissingName_ShouldReturnBadRequest()
    {
        // Arrange - Get existing method
        var allResponse = await _adminClient!.GetAsync("/api/payment-methods");
        var allMethods = await allResponse.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        var existingMethod = allMethods!.First();

        var updateRequest = new UpdatePaymentMethodRequest
        {
            Name = "", // Empty name
            Description = "Test"
        };

        // Act
        var response = await _adminClient!.PutAsJsonAsync($"/api/payment-methods/{existingMethod.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Update_AsOperator_ShouldReturnForbidden()
    {
        // Arrange - Get existing method
        var allResponse = await _adminClient!.GetAsync("/api/payment-methods");
        var allMethods = await allResponse.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        var existingMethod = allMethods!.First();

        var updateRequest = new UpdatePaymentMethodRequest
        {
            Name = "Operator Update",
            Description = "Should be forbidden"
        };

        // Act
        var response = await _operatorClient!.PutAsJsonAsync($"/api/payment-methods/{existingMethod.Id}", updateRequest);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region ChangeStatus Tests

    [Fact]
    public async Task ChangeStatus_Activate_ShouldReturnOk()
    {
        // Arrange - Create and deactivate a payment method
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "ACTIVATE_TEST",
            Name = "Activation Test",
            Description = "Test activation"
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<PaymentMethodDto>();

        // Deactivate first
        await _adminClient!.PatchAsJsonAsync(
            $"/api/payment-methods/{created!.Id}/status",
            new { IsActive = false }
        );

        // Act - Reactivate
        var response = await _adminClient!.PatchAsJsonAsync(
            $"/api/payment-methods/{created.Id}/status",
            new { IsActive = true }
        );

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var updated = await response.Content.ReadFromJsonAsync<PaymentMethodDto>();
        updated.Should().NotBeNull();
        updated!.IsActive.Should().BeTrue();
    }

    [Fact]
    public async Task ChangeStatus_Deactivate_ShouldReturnOk()
    {
        // Arrange - Create a payment method
        var createRequest = new CreatePaymentMethodRequest
        {
            Code = "DEACTIVATE_TEST",
            Name = "Deactivation Test",
            Description = "Test deactivation"
        };
        var createResponse = await _adminClient!.PostAsJsonAsync("/api/payment-methods", createRequest);
        var created = await createResponse.Content.ReadFromJsonAsync<PaymentMethodDto>();

        // Act
        var response = await _adminClient!.PatchAsJsonAsync(
            $"/api/payment-methods/{created!.Id}/status",
            new { IsActive = false }
        );

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var updated = await response.Content.ReadFromJsonAsync<PaymentMethodDto>();
        updated.Should().NotBeNull();
        updated!.IsActive.Should().BeFalse();
    }

    [Fact]
    public async Task ChangeStatus_WithNonExistentId_ShouldReturnNotFound()
    {
        // Act
        var response = await _adminClient!.PatchAsJsonAsync(
            $"/api/payment-methods/{Guid.NewGuid()}/status",
            new { IsActive = false }
        );

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task ChangeStatus_AsOperator_ShouldReturnForbidden()
    {
        // Arrange - Get existing method
        var allResponse = await _adminClient!.GetAsync("/api/payment-methods");
        var allMethods = await allResponse.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        var existingMethod = allMethods!.First();

        // Act
        var response = await _operatorClient!.PatchAsJsonAsync(
            $"/api/payment-methods/{existingMethod.Id}/status",
            new { IsActive = false }
        );

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    }

    #endregion

    #region Seed Data Tests

    [Fact]
    public async Task SeedData_ShouldCreatePredefinedPaymentMethods()
    {
        // Act
        var response = await _adminClient!.GetAsync("/api/payment-methods");
        var paymentMethods = await response.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();

        // Assert - Verify all predefined payment methods exist
        var expectedMethods = new[]
        {
            ("CASH", "Efectivo"),
            ("BIZUM", "Bizum"),
            ("TRANSFER", "Transferencia"),
            ("CARD_OWN", "Tarjeta propia"),
            ("CARD_POS", "Tarjeta TPV"),
            ("PAYPAL", "PayPal")
        };

        foreach (var (code, name) in expectedMethods)
        {
            var method = paymentMethods!.FirstOrDefault(pm => pm.Code == code);
            method.Should().NotBeNull($"Payment method {code} should exist");
            method!.Name.Should().Be(name);
            method.IsActive.Should().BeTrue($"Payment method {code} should be active by default");
        }

        var giftCard = paymentMethods!.FirstOrDefault(pm => pm.Code == "GIFT_CARD");
        giftCard.Should().NotBeNull("GIFT_CARD seed method should exist");
        giftCard!.Name.Should().Be("Tarjeta regalo");
    }

    [Fact]
    public async Task Seed_GiftCardMethod_IsHiddenAndNotDeactivatable()
    {
        var methodsResponse = await _adminClient!.GetAsync("/api/payment-methods");
        var methods = await methodsResponse.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        var giftCard = methods!.First(pm => pm.Code == "GIFT_CARD");

        var deactivateResponse = await _adminClient.PatchAsJsonAsync(
            $"/api/payment-methods/{giftCard.Id}/status",
            new { isActive = false });
        deactivateResponse.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task SeedData_ShouldBeIdempotent()
    {
        // Arrange - Run seed data multiple times by resetting database
        await _factory.ResetDatabaseAsync();
        
        // Act - Get payment methods after first seed
        var response1 = await _adminClient!.GetAsync("/api/payment-methods");
        var methods1 = await response1.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();

        // Reset database again (seed runs again)
        await _factory.ResetDatabaseAsync();
        
        var response2 = await _adminClient!.GetAsync("/api/payment-methods");
        var methods2 = await response2.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();

        // Assert - Should have same number of predefined methods
        methods2!.Count(pm => new[] { "CASH", "BIZUM", "TRANSFER", "CARD_OWN", "CARD_POS", "PAYPAL" }.Contains(pm.Code))
            .Should().Be(6, "Seed data should be idempotent and not create duplicates");
    }

    #endregion

    #region Integration with Point of Sale Tests

    [Fact]
    public async Task PaymentMethodAssignment_ShouldWorkWithPointOfSale()
    {
        // This test verifies the integration between payment methods and point of sale assignments
        // The actual assignment endpoints are in PointOfSalesController

        // Arrange - Create a point of sale
        using var scope = _factory.Services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        
        var pointOfSale = new PointOfSale
        {
            Id = Guid.NewGuid(),
            Name = "Test Store",
            Code = "TEST-001",
            Address = "123 Test St",
            IsActive = true,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        context.PointOfSales.Add(pointOfSale);
        await context.SaveChangesAsync();

        // Get a payment method
        var response = await _adminClient!.GetAsync("/api/payment-methods");
        var methods = await response.Content.ReadFromJsonAsync<List<PaymentMethodDto>>();
        var cashMethod = methods!.First(pm => pm.Code == "CASH");

        // Act - Assign payment method to point of sale (using PointOfSalesController)
        var assignResponse = await _adminClient!.PostAsync(
            $"/api/point-of-sales/{pointOfSale.Id}/payment-methods/{cashMethod.Id}",
            null
        );

        // Assert
        assignResponse.StatusCode.Should().Be(HttpStatusCode.Created);
    }

    #endregion
}
