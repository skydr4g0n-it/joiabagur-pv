using FluentAssertions;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Domain.Interfaces.Services;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.Logging;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Unit tests for ProductService.
/// </summary>
public class ProductServiceTests
{
    private readonly Mock<IProductRepository> _productRepositoryMock;
    private readonly Mock<ICollectionRepository> _collectionRepositoryMock;
    private readonly Mock<IInventoryRepository> _inventoryRepositoryMock;
    private readonly Mock<IUserPointOfSaleService> _userPointOfSaleServiceMock;
    private readonly Mock<IFileStorageService> _fileStorageServiceMock;
    private readonly Mock<IUnitOfWork> _unitOfWorkMock;
    private readonly Mock<ILogger<ProductService>> _loggerMock;
    private readonly ProductService _sut;

    public ProductServiceTests()
    {
        _productRepositoryMock = new Mock<IProductRepository>();
        _collectionRepositoryMock = new Mock<ICollectionRepository>();
        _inventoryRepositoryMock = new Mock<IInventoryRepository>();
        _userPointOfSaleServiceMock = new Mock<IUserPointOfSaleService>();
        _fileStorageServiceMock = new Mock<IFileStorageService>();
        _unitOfWorkMock = new Mock<IUnitOfWork>();
        _loggerMock = new Mock<ILogger<ProductService>>();

        _sut = new ProductService(
            _productRepositoryMock.Object,
            _collectionRepositoryMock.Object,
            _inventoryRepositoryMock.Object,
            _userPointOfSaleServiceMock.Object,
            _fileStorageServiceMock.Object,
            _unitOfWorkMock.Object,
            _loggerMock.Object);
    }

    #region GetAllAsync Tests

    [Fact]
    public async Task GetAllAsync_ShouldReturnAllProducts()
    {
        // Arrange
        var products = TestDataGenerator.CreateProducts(3);
        _productRepositoryMock.Setup(x => x.GetAllAsync(true))
            .ReturnsAsync(products);

        // Act
        var result = await _sut.GetAllAsync();

        // Assert
        result.Should().HaveCount(3);
        result.Select(p => p.SKU).Should().BeEquivalentTo(products.Select(p => p.SKU));
    }

    [Fact]
    public async Task GetAllAsync_WithIncludeInactiveFalse_ShouldFilterInactiveProducts()
    {
        // Arrange
        var activeProducts = TestDataGenerator.CreateProducts(2, isActive: true);
        _productRepositoryMock.Setup(x => x.GetAllAsync(false))
            .ReturnsAsync(activeProducts);

        // Act
        var result = await _sut.GetAllAsync(includeInactive: false);

        // Assert
        result.Should().HaveCount(2);
        result.Should().OnlyContain(p => p.IsActive);
    }

    #endregion

    #region GetByIdAsync Tests

    [Fact]
    public async Task GetByIdAsync_WithValidId_ShouldReturnProduct()
    {
        // Arrange
        var product = TestDataGenerator.CreateProduct();
        _productRepositoryMock.Setup(x => x.GetWithPhotosAsync(product.Id))
            .ReturnsAsync(product);

        // Act
        var result = await _sut.GetByIdAsync(product.Id);

        // Assert
        result.Should().NotBeNull();
        result!.Id.Should().Be(product.Id);
        result.SKU.Should().Be(product.SKU);
        result.Name.Should().Be(product.Name);
    }

    [Fact]
    public async Task GetByIdAsync_WithInvalidId_ShouldReturnNull()
    {
        // Arrange
        var productId = Guid.NewGuid();
        _productRepositoryMock.Setup(x => x.GetWithPhotosAsync(productId))
            .ReturnsAsync((Product?)null);

        // Act
        var result = await _sut.GetByIdAsync(productId);

        // Assert
        result.Should().BeNull();
    }

    #endregion

    #region CreateAsync Tests

    [Fact]
    public async Task CreateAsync_WithValidData_ShouldCreateProduct()
    {
        // Arrange
        var request = new CreateProductRequest
        {
            SKU = "JOY-NEW-001",
            Name = "New Gold Ring",
            Description = "Beautiful gold ring",
            Price = 299.99m
        };

        _productRepositoryMock.Setup(x => x.SkuExistsAsync(request.SKU, null))
            .ReturnsAsync(false);
        _productRepositoryMock.Setup(x => x.AddAsync(It.IsAny<Product>()))
            .ReturnsAsync((Product p) => p);

        // Act
        var result = await _sut.CreateAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.SKU.Should().Be(request.SKU);
        result.Name.Should().Be(request.Name);
        result.Price.Should().Be(request.Price);
        result.IsActive.Should().BeTrue();

        _productRepositoryMock.Verify(x => x.AddAsync(It.IsAny<Product>()), Times.Once);
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task CreateAsync_WithDuplicateSku_ShouldThrowDomainException()
    {
        // Arrange
        var request = new CreateProductRequest
        {
            SKU = "JOY-001",
            Name = "Gold Ring",
            Price = 299.99m
        };

        _productRepositoryMock.Setup(x => x.SkuExistsAsync(request.SKU, null))
            .ReturnsAsync(true);

        // Act
        var act = () => _sut.CreateAsync(request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*ya existe*");
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(-100.50)]
    public async Task CreateAsync_WithInvalidPrice_ShouldThrowDomainException(decimal price)
    {
        // Arrange
        var request = new CreateProductRequest
        {
            SKU = "JOY-001",
            Name = "Gold Ring",
            Price = price
        };

        _productRepositoryMock.Setup(x => x.SkuExistsAsync(request.SKU, null))
            .ReturnsAsync(false);

        // Act
        var act = () => _sut.CreateAsync(request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*mayor que cero*");
    }

    [Fact]
    public async Task CreateAsync_WithNonExistentCollection_ShouldThrowDomainException()
    {
        // Arrange
        var nonExistentCollectionId = Guid.NewGuid();
        var request = new CreateProductRequest
        {
            SKU = "JOY-001",
            Name = "Gold Ring",
            Price = 299.99m,
            CollectionId = nonExistentCollectionId
        };

        _productRepositoryMock.Setup(x => x.SkuExistsAsync(request.SKU, null))
            .ReturnsAsync(false);
        _collectionRepositoryMock.Setup(x => x.ExistsAsync(nonExistentCollectionId))
            .ReturnsAsync(false);

        // Act
        var act = () => _sut.CreateAsync(request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*no encontrad*");
    }

    #endregion

    #region UpdateAsync Tests

    [Fact]
    public async Task UpdateAsync_WithValidData_ShouldUpdateProduct()
    {
        // Arrange
        var product = TestDataGenerator.CreateProduct();
        var request = new UpdateProductRequest
        {
            Name = "Updated Gold Ring",
            Description = "Updated description",
            Price = 399.99m,
            IsActive = true
        };

        _productRepositoryMock.Setup(x => x.GetByIdAsync(product.Id))
            .ReturnsAsync(product);
        _productRepositoryMock.Setup(x => x.UpdateAsync(It.IsAny<Product>()))
            .ReturnsAsync((Product p) => p);

        // Act
        var result = await _sut.UpdateAsync(product.Id, request);

        // Assert
        result.Should().NotBeNull();
        result.Name.Should().Be(request.Name);
        result.Description.Should().Be(request.Description);
        result.Price.Should().Be(request.Price);

        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task UpdateAsync_WithNonExistentProduct_ShouldThrowDomainException()
    {
        // Arrange
        var productId = Guid.NewGuid();
        var request = new UpdateProductRequest
        {
            Name = "Updated Gold Ring",
            Price = 399.99m
        };

        _productRepositoryMock.Setup(x => x.GetByIdAsync(productId))
            .ReturnsAsync((Product?)null);

        // Act
        var act = () => _sut.UpdateAsync(productId, request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*no encontrad*");
    }

    #endregion

    #region DeactivateAsync Tests

    [Fact]
    public async Task DeactivateAsync_WithValidProduct_ShouldSetIsActiveFalse()
    {
        // Arrange
        var product = TestDataGenerator.CreateProduct(isActive: true);
        _productRepositoryMock.Setup(x => x.GetByIdAsync(product.Id))
            .ReturnsAsync(product);

        // Act
        await _sut.DeactivateAsync(product.Id);

        // Assert
        product.IsActive.Should().BeFalse();
        _productRepositoryMock.Verify(x => x.UpdateAsync(It.Is<Product>(p => !p.IsActive)), Times.Once);
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task DeactivateAsync_WithNonExistentProduct_ShouldThrowDomainException()
    {
        // Arrange
        var productId = Guid.NewGuid();
        _productRepositoryMock.Setup(x => x.GetByIdAsync(productId))
            .ReturnsAsync((Product?)null);

        // Act
        var act = () => _sut.DeactivateAsync(productId);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*no encontrad*");
    }

    #endregion

    #region SearchProductsAsync Tests

    [Fact]
    public async Task Search_SystemProductSku_ReturnsEmpty()
    {
        _productRepositoryMock.Setup(x => x.GetAllAsync(false))
            .ReturnsAsync(new List<Product>());

        var result = await _sut.SearchProductsAsync(GiftCardConstants.SystemProductSku, isAdmin: true);

        result.Should().BeEmpty();
    }

    #endregion

    #region ActivateAsync Tests

    [Fact]
    public async Task ActivateAsync_WithValidProduct_ShouldSetIsActiveTrue()
    {
        // Arrange
        var product = TestDataGenerator.CreateProduct(isActive: false);
        _productRepositoryMock.Setup(x => x.GetByIdAsync(product.Id))
            .ReturnsAsync(product);

        // Act
        await _sut.ActivateAsync(product.Id);

        // Assert
        product.IsActive.Should().BeTrue();
        _productRepositoryMock.Verify(x => x.UpdateAsync(It.Is<Product>(p => p.IsActive)), Times.Once);
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    #endregion
}




