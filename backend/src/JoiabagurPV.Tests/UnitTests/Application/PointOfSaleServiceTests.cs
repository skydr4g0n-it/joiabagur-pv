using FluentAssertions;
using JoiabagurPV.Application.DTOs.PointOfSales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.Logging;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// Unit tests for PointOfSaleService.
/// </summary>
public class PointOfSaleServiceTests
{
    private readonly Mock<IPointOfSaleRepository> _pointOfSaleRepositoryMock;
    private readonly Mock<IUserPointOfSaleRepository> _userPointOfSaleRepositoryMock;
    private readonly Mock<IPaymentMethodRepository> _paymentMethodRepositoryMock;
    private readonly Mock<IPaymentMethodService> _paymentMethodServiceMock;
    private readonly Mock<IUnitOfWork> _unitOfWorkMock;
    private readonly Mock<ILogger<PointOfSaleService>> _loggerMock;
    private readonly PointOfSaleService _sut;

    public PointOfSaleServiceTests()
    {
        _pointOfSaleRepositoryMock = new Mock<IPointOfSaleRepository>();
        _userPointOfSaleRepositoryMock = new Mock<IUserPointOfSaleRepository>();
        _paymentMethodRepositoryMock = new Mock<IPaymentMethodRepository>();
        _paymentMethodServiceMock = new Mock<IPaymentMethodService>();
        _unitOfWorkMock = new Mock<IUnitOfWork>();
        _loggerMock = new Mock<ILogger<PointOfSaleService>>();

        _sut = new PointOfSaleService(
            _pointOfSaleRepositoryMock.Object,
            _userPointOfSaleRepositoryMock.Object,
            _paymentMethodRepositoryMock.Object,
            _paymentMethodServiceMock.Object,
            _unitOfWorkMock.Object,
            _loggerMock.Object);
    }

    #region GetAllAsync Tests

    [Fact]
    public async Task GetAllAsync_ShouldReturnAllPointOfSales()
    {
        // Arrange
        var pointOfSales = TestDataGenerator.CreatePointOfSales(3);
        _pointOfSaleRepositoryMock.Setup(x => x.GetAllAsync(true))
            .ReturnsAsync(pointOfSales);

        // Act
        var result = await _sut.GetAllAsync(includeInactive: true);

        // Assert
        result.Should().HaveCount(3);
    }

    [Fact]
    public async Task GetAllAsync_WithIncludeInactiveFalse_ShouldFilterInactive()
    {
        // Arrange
        var activePointOfSales = TestDataGenerator.CreatePointOfSales(2, isActive: true);
        _pointOfSaleRepositoryMock.Setup(x => x.GetAllAsync(false))
            .ReturnsAsync(activePointOfSales);

        // Act
        var result = await _sut.GetAllAsync(includeInactive: false);

        // Assert
        result.Should().HaveCount(2);
        result.Should().OnlyContain(p => p.IsActive);
    }

    [Fact]
    public async Task GetAllAsync_WithNoPointOfSales_ShouldReturnEmptyList()
    {
        // Arrange
        _pointOfSaleRepositoryMock.Setup(x => x.GetAllAsync(true))
            .ReturnsAsync(new List<PointOfSale>());

        // Act
        var result = await _sut.GetAllAsync();

        // Assert
        result.Should().BeEmpty();
    }

    #endregion

    #region GetByUserAsync Tests

    [Fact]
    public async Task GetByUserAsync_ShouldReturnAssignedPointOfSales()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var pointOfSales = TestDataGenerator.CreatePointOfSales(2);
        _pointOfSaleRepositoryMock.Setup(x => x.GetByUserAsync(userId, false))
            .ReturnsAsync(pointOfSales);

        // Act
        var result = await _sut.GetByUserAsync(userId);

        // Assert
        result.Should().HaveCount(2);
    }

    [Fact]
    public async Task GetByUserAsync_WithNoAssignments_ShouldReturnEmptyList()
    {
        // Arrange
        var userId = Guid.NewGuid();
        _pointOfSaleRepositoryMock.Setup(x => x.GetByUserAsync(userId, false))
            .ReturnsAsync(new List<PointOfSale>());

        // Act
        var result = await _sut.GetByUserAsync(userId);

        // Assert
        result.Should().BeEmpty();
    }

    #endregion

    #region GetByIdAsync Tests

    [Fact]
    public async Task GetByIdAsync_WithValidId_ShouldReturnPointOfSale()
    {
        // Arrange
        var pointOfSale = TestDataGenerator.CreatePointOfSale();
        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(pointOfSale.Id))
            .ReturnsAsync(pointOfSale);

        // Act
        var result = await _sut.GetByIdAsync(pointOfSale.Id);

        // Assert
        result.Should().NotBeNull();
        result!.Id.Should().Be(pointOfSale.Id);
        result.Name.Should().Be(pointOfSale.Name);
        result.Code.Should().Be(pointOfSale.Code);
    }

    [Fact]
    public async Task GetByIdAsync_WithInvalidId_ShouldReturnNull()
    {
        // Arrange
        var id = Guid.NewGuid();
        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(id))
            .ReturnsAsync((PointOfSale?)null);

        // Act
        var result = await _sut.GetByIdAsync(id);

        // Assert
        result.Should().BeNull();
    }

    #endregion

    #region CreateAsync Tests

    [Fact]
    public async Task CreateAsync_WithValidData_ShouldCreatePointOfSale()
    {
        // Arrange
        var request = new CreatePointOfSaleRequest
        {
            Name = "Test Store",
            Code = "TS-001",
            Address = "123 Test St",
            Phone = "555-1234",
            Email = "test@store.com"
        };

        _pointOfSaleRepositoryMock.Setup(x => x.CodeExistsAsync(request.Code, null))
            .ReturnsAsync(false);

        // Act
        var result = await _sut.CreateAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.Name.Should().Be(request.Name);
        result.Code.Should().Be(request.Code.ToUpperInvariant());
        result.Address.Should().Be(request.Address);
        result.Phone.Should().Be(request.Phone);
        result.Email.Should().Be(request.Email);
        result.IsActive.Should().BeTrue();

        _pointOfSaleRepositoryMock.Verify(x => x.AddAsync(It.Is<PointOfSale>(p =>
            p.Name == request.Name &&
            p.Code == request.Code.ToUpperInvariant() &&
            p.IsActive)), Times.Once);
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task CreateAsync_WithDuplicateCode_ShouldThrowDomainException()
    {
        // Arrange
        var request = new CreatePointOfSaleRequest
        {
            Name = "Test Store",
            Code = "TS-001"
        };

        _pointOfSaleRepositoryMock.Setup(x => x.CodeExistsAsync(request.Code, null))
            .ReturnsAsync(true);

        // Act
        var act = () => _sut.CreateAsync(request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("El código de punto de venta ya está en uso");
    }

    [Fact]
    public async Task CreateAsync_ShouldConvertCodeToUpperCase()
    {
        // Arrange
        var request = new CreatePointOfSaleRequest
        {
            Name = "Test Store",
            Code = "ts-001"
        };

        _pointOfSaleRepositoryMock.Setup(x => x.CodeExistsAsync(request.Code, null))
            .ReturnsAsync(false);

        // Act
        var result = await _sut.CreateAsync(request);

        // Assert
        result.Code.Should().Be("TS-001");
    }

    #endregion

    #region UpdateAsync Tests

    [Fact]
    public async Task UpdateAsync_WithValidData_ShouldUpdatePointOfSale()
    {
        // Arrange
        var pointOfSale = TestDataGenerator.CreatePointOfSale();
        var request = new UpdatePointOfSaleRequest
        {
            Name = "Updated Name",
            Address = "New Address",
            Phone = "555-9999",
            Email = "updated@store.com",
            IsActive = true
        };

        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(pointOfSale.Id))
            .ReturnsAsync(pointOfSale);

        // Act
        var result = await _sut.UpdateAsync(pointOfSale.Id, request);

        // Assert
        result.Should().NotBeNull();
        result.Name.Should().Be(request.Name);
        result.Address.Should().Be(request.Address);
        result.Phone.Should().Be(request.Phone);
        result.Email.Should().Be(request.Email);

        _pointOfSaleRepositoryMock.Verify(x => x.UpdateAsync(pointOfSale), Times.Once);
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task UpdateAsync_WithNonExistentId_ShouldThrowDomainException()
    {
        // Arrange
        var id = Guid.NewGuid();
        var request = new UpdatePointOfSaleRequest
        {
            Name = "Updated Name",
            IsActive = true
        };

        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(id))
            .ReturnsAsync((PointOfSale?)null);

        // Act
        var act = () => _sut.UpdateAsync(id, request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("Punto de venta no encontrado");
    }

    #endregion

    #region ChangeStatusAsync Tests

    [Fact]
    public async Task ChangeStatusAsync_ActivatePointOfSale_ShouldSetIsActiveTrue()
    {
        // Arrange
        var pointOfSale = TestDataGenerator.CreatePointOfSale(isActive: false);
        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(pointOfSale.Id))
            .ReturnsAsync(pointOfSale);

        // Act
        var result = await _sut.ChangeStatusAsync(pointOfSale.Id, isActive: true);

        // Assert
        result.IsActive.Should().BeTrue();
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task ChangeStatusAsync_DeactivateWithoutAssignments_ShouldSetIsActiveFalse()
    {
        // Arrange
        var pointOfSale = TestDataGenerator.CreatePointOfSale(isActive: true);
        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(pointOfSale.Id))
            .ReturnsAsync(pointOfSale);
        _pointOfSaleRepositoryMock.Setup(x => x.HasActiveAssignmentsAsync(pointOfSale.Id))
            .ReturnsAsync(false);

        // Act
        var result = await _sut.ChangeStatusAsync(pointOfSale.Id, isActive: false);

        // Assert
        result.IsActive.Should().BeFalse();
        _unitOfWorkMock.Verify(x => x.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task ChangeStatusAsync_DeactivateWithActiveAssignments_ShouldThrowDomainException()
    {
        // Arrange
        var pointOfSale = TestDataGenerator.CreatePointOfSale(isActive: true);
        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(pointOfSale.Id))
            .ReturnsAsync(pointOfSale);
        _pointOfSaleRepositoryMock.Setup(x => x.HasActiveAssignmentsAsync(pointOfSale.Id))
            .ReturnsAsync(true);

        // Act
        var act = () => _sut.ChangeStatusAsync(pointOfSale.Id, isActive: false);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("No se puede desactivar punto de venta con operadores asignados activos");
    }

    [Fact]
    public async Task ChangeStatusAsync_WithNonExistentId_ShouldThrowDomainException()
    {
        // Arrange
        var id = Guid.NewGuid();
        _pointOfSaleRepositoryMock.Setup(x => x.GetByIdAsync(id))
            .ReturnsAsync((PointOfSale?)null);

        // Act
        var act = () => _sut.ChangeStatusAsync(id, isActive: true);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("Punto de venta no encontrado");
    }

    #endregion

    #region UserHasAccessAsync Tests

    [Fact]
    public async Task UserHasAccessAsync_WithActiveAssignment_ShouldReturnTrue()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var pointOfSaleId = Guid.NewGuid();
        var assignment = TestDataGenerator.CreateUserPointOfSale(userId, pointOfSaleId, isActive: true);

        _userPointOfSaleRepositoryMock.Setup(x => x.GetAssignmentAsync(userId, pointOfSaleId))
            .ReturnsAsync(assignment);

        // Act
        var result = await _sut.UserHasAccessAsync(userId, pointOfSaleId);

        // Assert
        result.Should().BeTrue();
    }

    [Fact]
    public async Task UserHasAccessAsync_WithInactiveAssignment_ShouldReturnFalse()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var pointOfSaleId = Guid.NewGuid();
        var assignment = TestDataGenerator.CreateUserPointOfSale(userId, pointOfSaleId, isActive: false);

        _userPointOfSaleRepositoryMock.Setup(x => x.GetAssignmentAsync(userId, pointOfSaleId))
            .ReturnsAsync(assignment);

        // Act
        var result = await _sut.UserHasAccessAsync(userId, pointOfSaleId);

        // Assert
        result.Should().BeFalse();
    }

    [Fact]
    public async Task UserHasAccessAsync_WithNoAssignment_ShouldReturnFalse()
    {
        // Arrange
        var userId = Guid.NewGuid();
        var pointOfSaleId = Guid.NewGuid();

        _userPointOfSaleRepositoryMock.Setup(x => x.GetAssignmentAsync(userId, pointOfSaleId))
            .ReturnsAsync((UserPointOfSale?)null);

        // Act
        var result = await _sut.UserHasAccessAsync(userId, pointOfSaleId);

        // Assert
        result.Should().BeFalse();
    }

    #endregion
}
