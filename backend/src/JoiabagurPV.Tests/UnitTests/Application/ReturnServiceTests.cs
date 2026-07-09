using FluentAssertions;
using JoiabagurPV.Application.DTOs.Returns;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using JoiabagurPV.Tests.TestHelpers;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Unit tests for ReturnService.
/// Note: Most business logic is tested via integration tests due to EF Core async patterns.
/// These tests cover basic validation and error cases that don't require complex mocking.
/// </summary>
public class ReturnServiceTests
{
    private readonly Mock<IReturnRepository> _returnRepositoryMock;
    private readonly Mock<IReturnSaleRepository> _returnSaleRepositoryMock;
    private readonly Mock<IReturnPhotoRepository> _returnPhotoRepositoryMock;
    private readonly Mock<ISaleRepository> _saleRepositoryMock;
    private readonly Mock<IProductRepository> _productRepositoryMock;
    private readonly Mock<IUserPointOfSaleRepository> _userPointOfSaleRepositoryMock;
    private readonly Mock<IInventoryService> _inventoryServiceMock;
    private readonly Mock<IFileStorageService> _fileStorageServiceMock;
    private readonly Mock<IUnitOfWork> _unitOfWorkMock;
    private readonly Mock<IDashboardService> _dashboardServiceMock;
    private readonly ReturnService _sut;

    public ReturnServiceTests()
    {
        _returnRepositoryMock = new Mock<IReturnRepository>();
        _returnSaleRepositoryMock = new Mock<IReturnSaleRepository>();
        _returnPhotoRepositoryMock = new Mock<IReturnPhotoRepository>();
        _saleRepositoryMock = new Mock<ISaleRepository>();
        _productRepositoryMock = new Mock<IProductRepository>();
        _userPointOfSaleRepositoryMock = new Mock<IUserPointOfSaleRepository>();
        _inventoryServiceMock = new Mock<IInventoryService>();
        _fileStorageServiceMock = new Mock<IFileStorageService>();
        _unitOfWorkMock = new Mock<IUnitOfWork>();
        _dashboardServiceMock = new Mock<IDashboardService>();

        _sut = new ReturnService(
            _returnRepositoryMock.Object,
            _returnSaleRepositoryMock.Object,
            _returnPhotoRepositoryMock.Object,
            _saleRepositoryMock.Object,
            _productRepositoryMock.Object,
            _userPointOfSaleRepositoryMock.Object,
            _inventoryServiceMock.Object,
            _fileStorageServiceMock.Object,
            _unitOfWorkMock.Object,
            _dashboardServiceMock.Object);
    }

    #region CreateReturn Validation Tests

    [Fact]
    public async Task CreateReturn_WithEmptySaleAssociations_ReturnsError()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var posId = Guid.NewGuid();

        var request = new CreateReturnRequest
        {
            ProductId = Guid.NewGuid(),
            PointOfSaleId = posId,
            Quantity = 2,
            Category = ReturnCategory.Defectuoso,
            SaleAssociations = new List<SaleAssociationRequest>() // Empty
        };

        // Act
        var result = await _sut.CreateReturnAsync(request, userId, isAdmin: true); // Admin to bypass POS check

        // Assert
        result.Success.Should().BeFalse();
        result.ErrorMessage.Should().NotBeNullOrEmpty();
    }

    [Fact]
    public async Task CreateReturn_WithZeroQuantity_ReturnsError()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var posId = Guid.NewGuid();

        var request = new CreateReturnRequest
        {
            ProductId = Guid.NewGuid(),
            PointOfSaleId = posId,
            Quantity = 0, // Invalid
            Category = ReturnCategory.Defectuoso,
            SaleAssociations = new List<SaleAssociationRequest>
            {
                new() { SaleId = Guid.NewGuid(), Quantity = 0 }
            }
        };

        // Act
        var result = await _sut.CreateReturnAsync(request, userId, isAdmin: true);

        // Assert
        result.Success.Should().BeFalse();
    }

    [Fact]
    public async Task CreateReturn_WithMismatchedQuantitySum_ReturnsError()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var posId = Guid.NewGuid();

        var request = new CreateReturnRequest
        {
            ProductId = Guid.NewGuid(),
            PointOfSaleId = posId,
            Quantity = 5, // Total quantity
            Category = ReturnCategory.Defectuoso,
            SaleAssociations = new List<SaleAssociationRequest>
            {
                new() { SaleId = Guid.NewGuid(), Quantity = 2 } // Only 2, not 5
            }
        };

        // Act
        var result = await _sut.CreateReturnAsync(request, userId, isAdmin: true);

        // Assert
        result.Success.Should().BeFalse();
    }

    [Theory]
    [InlineData(ReturnCategory.Defectuoso)]
    [InlineData(ReturnCategory.TamañoIncorrecto)]
    [InlineData(ReturnCategory.NoSatisfecho)]
    [InlineData(ReturnCategory.Otro)]
    public void ReturnCategory_AllValues_AreValid(ReturnCategory category)
    {
        // Assert - All enum values exist and are not zero (except if explicitly designed that way)
        category.Should().BeOneOf(
            ReturnCategory.Defectuoso,
            ReturnCategory.TamañoIncorrecto,
            ReturnCategory.NoSatisfecho,
            ReturnCategory.Otro);
    }

    #endregion

    #region GetReturnPhotoPath Tests

    [Fact]
    public async Task GetReturnPhotoPath_WhenNoPhotoExists_ReturnsNull()
    {
        // Arrange
        var returnId = Guid.NewGuid();
        _returnPhotoRepositoryMock.Setup(x => x.GetByReturnIdAsync(returnId))
            .ReturnsAsync((ReturnPhoto?)null);

        // Act
        var result = await _sut.GetReturnPhotoPathAsync(returnId);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public async Task GetReturnPhotoPath_WhenPhotoExists_ReturnsFilePath()
    {
        // Arrange
        var returnId = Guid.NewGuid();
        var photo = new ReturnPhoto
        {
            Id = Guid.NewGuid(),
            ReturnId = returnId,
            FilePath = "/uploads/returns/test.jpg",
            FileName = "test.jpg",
            FileSize = 1024,
            MimeType = "image/jpeg"
        };
        _returnPhotoRepositoryMock.Setup(x => x.GetByReturnIdAsync(returnId))
            .ReturnsAsync(photo);

        // Act
        var result = await _sut.GetReturnPhotoPathAsync(returnId);

        // Assert
        result.Should().Be("/uploads/returns/test.jpg");
    }

    #endregion

    #region Entity Tests

    [Fact]
    public void Return_GetTotalValue_CalculatesCorrectly()
    {
        // Arrange
        var returnEntity = TestDataGenerator.CreateReturn(quantity: 5);
        returnEntity.ReturnSales = new List<ReturnSale>
        {
            TestDataGenerator.CreateReturnSale(returnId: returnEntity.Id, quantity: 2, unitPrice: 100m),
            TestDataGenerator.CreateReturnSale(returnId: returnEntity.Id, quantity: 3, unitPrice: 150m)
        };

        // Act
        var totalValue = returnEntity.GetTotalValue();

        // Assert
        totalValue.Should().Be(650m); // (2 * 100) + (3 * 150)
    }

    [Fact]
    public void Return_IsQuantityValid_ReturnsTrueForPositiveQuantity()
    {
        // Arrange
        var returnEntity = TestDataGenerator.CreateReturn(quantity: 5);

        // Act & Assert
        returnEntity.IsQuantityValid().Should().BeTrue();
    }

    [Fact]
    public void Return_IsQuantityValid_ReturnsFalseForZeroQuantity()
    {
        // Arrange
        var returnEntity = TestDataGenerator.CreateReturn(quantity: 0);

        // Act & Assert
        returnEntity.IsQuantityValid().Should().BeFalse();
    }

    [Fact]
    public void ReturnPhoto_IsFileSizeValid_ReturnsTrueForSmallFile()
    {
        // Arrange
        var photo = new ReturnPhoto
        {
            Id = Guid.NewGuid(),
            ReturnId = Guid.NewGuid(),
            FilePath = "/test.jpg",
            FileName = "test.jpg",
            FileSize = 1024 * 1024, // 1MB
            MimeType = "image/jpeg"
        };

        // Act & Assert
        photo.IsFileSizeValid().Should().BeTrue();
    }

    [Fact]
    public void ReturnPhoto_IsFileSizeValid_ReturnsFalseForLargeFile()
    {
        // Arrange
        var photo = new ReturnPhoto
        {
            Id = Guid.NewGuid(),
            ReturnId = Guid.NewGuid(),
            FilePath = "/test.jpg",
            FileName = "test.jpg",
            FileSize = 3 * 1024 * 1024, // 3MB (over 2MB limit)
            MimeType = "image/jpeg"
        };

        // Act & Assert
        photo.IsFileSizeValid().Should().BeFalse();
    }

    [Fact]
    public void ReturnPhoto_IsMimeTypeValid_ReturnsTrueForJpeg()
    {
        // Arrange
        var photo = new ReturnPhoto
        {
            Id = Guid.NewGuid(),
            ReturnId = Guid.NewGuid(),
            FilePath = "/test.jpg",
            FileName = "test.jpg",
            FileSize = 1024,
            MimeType = "image/jpeg"
        };

        // Act & Assert
        photo.IsMimeTypeValid().Should().BeTrue();
    }

    [Fact]
    public void ReturnPhoto_IsMimeTypeValid_ReturnsFalseForPng()
    {
        // Arrange
        var photo = new ReturnPhoto
        {
            Id = Guid.NewGuid(),
            ReturnId = Guid.NewGuid(),
            FilePath = "/test.png",
            FileName = "test.png",
            FileSize = 1024,
            MimeType = "image/png"
        };

        // Act & Assert
        photo.IsMimeTypeValid().Should().BeFalse();
    }

    #endregion
}
