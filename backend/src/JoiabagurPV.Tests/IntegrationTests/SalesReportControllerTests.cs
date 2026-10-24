using FluentAssertions;
using JoiabagurPV.Application.DTOs.Auth;
using JoiabagurPV.Application.DTOs.Sales;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Infrastructure.Data;
using JoiabagurPV.Tests.TestHelpers.Mothers;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using System.Net;
using System.Net.Http.Json;

namespace JoiabagurPV.Tests.IntegrationTests;

[Collection(IntegrationTestCollection.Name)]
public class SalesReportControllerTests : IAsyncLifetime
{
    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;
    private HttpClient? _adminClient;

    private Product _testProduct = null!;
    private PointOfSale _testPos = null!;
    private PaymentMethod _testPaymentMethod = null!;
    private User _testOperator = null!;

    public SalesReportControllerTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync()
    {
        await _factory.ResetDatabaseAsync();
        _adminClient = await CreateAuthenticatedClientAsync("admin", "Admin123!");
        await SetupTestDataAsync();
    }

    public Task DisposeAsync() => Task.CompletedTask;

    private async Task SetupTestDataAsync()
    {
        using var mother = new TestDataMother(_factory.Services);

        _testPos = await mother.PointOfSale()
            .WithCode("RPT-POS")
            .WithName("Report Test POS")
            .WithAddress("Test Address")
            .WithPhone("600000000")
            .CreateAsync();

        _testPaymentMethod = await mother.Context.PaymentMethods
            .FirstAsync(pm => pm.Code == "CASH");

        mother.Context.PointOfSalePaymentMethods.Add(new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = _testPos.Id,
            PaymentMethodId = _testPaymentMethod.Id,
            CreatedAt = DateTime.UtcNow
        });
        await mother.Context.SaveChangesAsync();

        _testProduct = await mother.Product()
            .WithSku("RPT-SKU-001")
            .WithName("Report Test Product")
            .WithPrice(50.00m)
            .CreateAsync();

        await mother.Inventory()
            .WithProduct(_testProduct.Id)
            .WithPointOfSale(_testPos.Id)
            .WithQuantity(100)
            .CreateAsync();

        _testOperator = await mother.User()
            .WithUsername("rptoperator")
            .WithName("Report", "Operator")
            .AsOperator()
            .AssignedTo(_testPos.Id)
            .CreateAsync();

        for (int i = 0; i < 5; i++)
        {
            await mother.Sale()
                .WithProduct(_testProduct.Id)
                .WithPointOfSale(_testPos.Id)
                .WithPaymentMethod(_testPaymentMethod.Id)
                .WithUser(_testOperator.Id)
                .WithQuantity(2)
                .WithPrice(50.00m)
                .WithSaleDate(DateTime.UtcNow.AddDays(-i))
                .CreateAsync();
        }
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

    [Fact]
    public async Task GetSalesReport_WithSeedData_ReturnsPaginatedResponseWithAggregates()
    {
        var response = await _adminClient!.GetAsync("/api/reports/sales");

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var result = await response.Content.ReadFromJsonAsync<SalesReportResponse>();
        result.Should().NotBeNull();
        result!.Items.Should().HaveCountGreaterOrEqualTo(1);
        result.TotalSalesCount.Should().Be(5);
        result.TotalQuantity.Should().Be(10);
        result.TotalAmount.Should().Be(500.00m);
        result.TotalCommission.Should().Be(0m);
        result.TotalAmountNet.Should().Be(500.00m);
    }

    [Fact]
    public async Task ExportSalesReport_WithinLimit_Returns200WithExcelContentType()
    {
        var response = await _adminClient!.GetAsync("/api/reports/sales/export");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType!.MediaType
            .Should().Be("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    }

    [Fact]
    public async Task GetSalesReport_Unauthenticated_Returns401()
    {
        var anonymousClient = _factory.CreateClient();
        var response = await anonymousClient.GetAsync("/api/reports/sales");

        response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    }
}
