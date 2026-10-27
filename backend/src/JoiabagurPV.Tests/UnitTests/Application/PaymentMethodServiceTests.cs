using FluentAssertions;
using JoiabagurPV.Application.DTOs.PaymentMethods;
using JoiabagurPV.Application.Services;
using JoiabagurPV.Domain.Constants;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;
using JoiabagurPV.Tests.TestHelpers;
using Microsoft.Extensions.Logging;
using Moq;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class PaymentMethodServiceTests
{
    private readonly Mock<IPaymentMethodRepository> _paymentMethodRepositoryMock;
    private readonly Mock<IPointOfSalePaymentMethodRepository> _posPaymentMethodRepositoryMock;
    private readonly Mock<IPointOfSaleRepository> _pointOfSaleRepositoryMock;
    private readonly Mock<IUnitOfWork> _unitOfWorkMock;
    private readonly Mock<ILogger<PaymentMethodService>> _loggerMock;
    private readonly PaymentMethodService _service;

    public PaymentMethodServiceTests()
    {
        _paymentMethodRepositoryMock = new Mock<IPaymentMethodRepository>();
        _posPaymentMethodRepositoryMock = new Mock<IPointOfSalePaymentMethodRepository>();
        _pointOfSaleRepositoryMock = new Mock<IPointOfSaleRepository>();
        _unitOfWorkMock = new Mock<IUnitOfWork>();
        _loggerMock = new Mock<ILogger<PaymentMethodService>>();

        _service = new PaymentMethodService(
            _paymentMethodRepositoryMock.Object,
            _posPaymentMethodRepositoryMock.Object,
            _pointOfSaleRepositoryMock.Object,
            _unitOfWorkMock.Object,
            _loggerMock.Object);
    }

    #region GetAllAsync Tests

    [Fact]
    public async Task GetAllAsync_ShouldReturnAllPaymentMethods()
    {
        // Arrange
        var pm1 = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        var pm2 = TestDataGenerator.CreatePaymentMethod(code: "BIZUM", name: "Bizum");
        var paymentMethods = new List<PaymentMethod> { pm1, pm2 };
        _paymentMethodRepositoryMock.Setup(r => r.GetAllAsync(true)).ReturnsAsync(paymentMethods);

        // Act
        var result = await _service.GetAllAsync(true);

        // Assert
        result.Should().HaveCount(2);
        result.Should().Contain(pm => pm.Code == "CASH");
        result.Should().Contain(pm => pm.Code == "BIZUM");
    }

    [Fact]
    public async Task GetAllAsync_WhenIncludeInactiveFalse_ShouldReturnOnlyActive()
    {
        // Arrange
        var pm = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        var activePaymentMethods = new List<PaymentMethod> { pm };
        _paymentMethodRepositoryMock.Setup(r => r.GetAllAsync(false)).ReturnsAsync(activePaymentMethods);

        // Act
        var result = await _service.GetAllAsync(false);

        // Assert
        result.Should().HaveCount(1);
        result.First().Code.Should().Be("CASH");
    }

    #endregion

    #region GetByIdAsync Tests

    [Fact]
    public async Task GetByIdAsync_WhenExists_ShouldReturnPaymentMethod()
    {
        // Arrange
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(paymentMethod.Id)).ReturnsAsync(paymentMethod);

        // Act
        var result = await _service.GetByIdAsync(paymentMethod.Id);

        // Assert
        result.Should().NotBeNull();
        result!.Code.Should().Be("CASH");
    }

    [Fact]
    public async Task GetByIdAsync_WhenNotExists_ShouldReturnNull()
    {
        // Arrange
        var id = Guid.NewGuid();
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(id)).ReturnsAsync((PaymentMethod?)null);

        // Act
        var result = await _service.GetByIdAsync(id);

        // Assert
        result.Should().BeNull();
    }

    #endregion

    #region CreateAsync Tests

    [Fact]
    public async Task CreateAsync_WithValidData_ShouldCreatePaymentMethod()
    {
        // Arrange
        var request = new CreatePaymentMethodRequest
        {
            Code = "NEWMETHOD",
            Name = "New Method",
            Description = "Description"
        };
        _paymentMethodRepositoryMock.Setup(r => r.CodeExistsAsync(request.Code, null)).ReturnsAsync(false);
        _paymentMethodRepositoryMock.Setup(r => r.AddAsync(It.IsAny<PaymentMethod>()))
            .ReturnsAsync((PaymentMethod pm) => pm);

        // Act
        var result = await _service.CreateAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.Code.Should().Be("NEWMETHOD");
        result.Name.Should().Be("New Method");
        result.IsActive.Should().BeTrue();
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task CreateAsync_WithDuplicateCode_ShouldThrowDomainException()
    {
        // Arrange
        var request = new CreatePaymentMethodRequest
        {
            Code = "CASH",
            Name = "Duplicate Cash"
        };
        _paymentMethodRepositoryMock.Setup(r => r.CodeExistsAsync(request.Code, null)).ReturnsAsync(true);

        // Act
        var act = () => _service.CreateAsync(request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*en uso*");
    }

    #endregion

    #region UpdateAsync Tests

    [Fact]
    public async Task UpdateAsync_WithValidData_ShouldUpdatePaymentMethod()
    {
        // Arrange
        var existingMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Old Name");
        var request = new UpdatePaymentMethodRequest
        {
            Name = "New Name",
            Description = "Updated description"
        };
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(existingMethod.Id)).ReturnsAsync(existingMethod);
        _paymentMethodRepositoryMock.Setup(r => r.UpdateAsync(It.IsAny<PaymentMethod>()))
            .ReturnsAsync((PaymentMethod pm) => pm);

        // Act
        var result = await _service.UpdateAsync(existingMethod.Id, request);

        // Assert
        result.Should().NotBeNull();
        result.Name.Should().Be("New Name");
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task UpdateAsync_WhenNotFound_ShouldThrowDomainException()
    {
        // Arrange
        var id = Guid.NewGuid();
        var request = new UpdatePaymentMethodRequest { Name = "Name" };
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(id)).ReturnsAsync((PaymentMethod?)null);

        // Act
        var act = () => _service.UpdateAsync(id, request);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*no encontrado*");
    }

    #endregion

    #region ChangeStatusAsync Tests

    [Fact]
    public async Task ChangeStatusAsync_ShouldUpdateStatus()
    {
        // Arrange
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Cash");
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(paymentMethod.Id)).ReturnsAsync(paymentMethod);
        _paymentMethodRepositoryMock.Setup(r => r.UpdateAsync(It.IsAny<PaymentMethod>()))
            .ReturnsAsync((PaymentMethod pm) => pm);

        // Act
        var result = await _service.ChangeStatusAsync(paymentMethod.Id, false);

        // Assert
        result.Should().NotBeNull();
        result.IsActive.Should().BeFalse();
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    #endregion

    #region AssignToPointOfSaleAsync Tests

    [Fact]
    public async Task AssignToPointOfSaleAsync_WithValidData_ShouldCreateAssignment()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Cash");
        
        _pointOfSaleRepositoryMock.Setup(r => r.ExistsAsync(pointOfSaleId)).ReturnsAsync(true);
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(paymentMethod.Id)).ReturnsAsync(paymentMethod);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync((PointOfSalePaymentMethod?)null);
        _posPaymentMethodRepositoryMock.Setup(r => r.AddAsync(It.IsAny<PointOfSalePaymentMethod>()))
            .ReturnsAsync((PointOfSalePaymentMethod pm) => pm);

        // Act
        var result = await _service.AssignToPointOfSaleAsync(pointOfSaleId, paymentMethod.Id);

        // Assert
        result.Should().NotBeNull();
        result.PointOfSaleId.Should().Be(pointOfSaleId);
        result.PaymentMethodId.Should().Be(paymentMethod.Id);
        result.IsActive.Should().BeTrue();
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task AssignToPointOfSaleAsync_WhenPointOfSaleNotFound_ShouldThrowDomainException()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethodId = Guid.NewGuid();
        _pointOfSaleRepositoryMock.Setup(r => r.ExistsAsync(pointOfSaleId)).ReturnsAsync(false);

        // Act
        var act = () => _service.AssignToPointOfSaleAsync(pointOfSaleId, paymentMethodId);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*Punto de venta no encontrado*");
    }

    [Fact]
    public async Task AssignToPointOfSaleAsync_WhenPaymentMethodNotFound_ShouldThrowDomainException()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethodId = Guid.NewGuid();
        _pointOfSaleRepositoryMock.Setup(r => r.ExistsAsync(pointOfSaleId)).ReturnsAsync(true);
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(paymentMethodId)).ReturnsAsync((PaymentMethod?)null);

        // Act
        var act = () => _service.AssignToPointOfSaleAsync(pointOfSaleId, paymentMethodId);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*Método de pago no encontrado*");
    }

    [Fact]
    public async Task AssignToPointOfSaleAsync_WhenAlreadyAssigned_ShouldThrowDomainException()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Cash");
        var existingAssignment = new PointOfSalePaymentMethod
        {
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethod.Id,
            IsActive = true,
            PaymentMethod = paymentMethod
        };

        _pointOfSaleRepositoryMock.Setup(r => r.ExistsAsync(pointOfSaleId)).ReturnsAsync(true);
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(paymentMethod.Id)).ReturnsAsync(paymentMethod);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync(existingAssignment);

        // Act
        var act = () => _service.AssignToPointOfSaleAsync(pointOfSaleId, paymentMethod.Id);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*ya está asignado*");
    }

    #endregion

    #region IsPaymentMethodAvailableAsync Tests

    [Fact]
    public async Task IsPaymentMethodAvailableAsync_WhenActiveAndAssigned_ShouldReturnTrue()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethodId = Guid.NewGuid();
        _posPaymentMethodRepositoryMock.Setup(r => r.IsActiveForPointOfSaleAsync(pointOfSaleId, paymentMethodId))
            .ReturnsAsync(true);

        // Act
        var result = await _service.IsPaymentMethodAvailableAsync(pointOfSaleId, paymentMethodId);

        // Assert
        result.Should().BeTrue();
    }

    [Fact]
    public async Task IsPaymentMethodAvailableAsync_WhenNotAssigned_ShouldReturnFalse()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethodId = Guid.NewGuid();
        _posPaymentMethodRepositoryMock.Setup(r => r.IsActiveForPointOfSaleAsync(pointOfSaleId, paymentMethodId))
            .ReturnsAsync(false);

        // Act
        var result = await _service.IsPaymentMethodAvailableAsync(pointOfSaleId, paymentMethodId);

        // Assert
        result.Should().BeFalse();
    }

    #endregion

    #region UnassignFromPointOfSaleAsync Tests

    [Fact]
    public async Task UnassignFromPointOfSaleAsync_WhenMultipleActivePaymentMethods_ShouldSucceed()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod();
        var assignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethod.Id,
            IsActive = true
        };

        var otherAssignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = Guid.NewGuid(),
            IsActive = true
        };

        var activeAssignments = new List<PointOfSalePaymentMethod> { assignment, otherAssignment };

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync(assignment);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetByPointOfSaleAsync(pointOfSaleId, false))
            .ReturnsAsync(activeAssignments);

        // Act
        await _service.UnassignFromPointOfSaleAsync(pointOfSaleId, paymentMethod.Id);

        // Assert
        _posPaymentMethodRepositoryMock.Verify(r => r.DeleteAsync(assignment.Id), Times.Once);
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task UnassignFromPointOfSaleAsync_WhenLastActivePaymentMethod_ShouldThrowException()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod();
        var assignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethod.Id,
            IsActive = true
        };

        var activeAssignments = new List<PointOfSalePaymentMethod> { assignment };

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync(assignment);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetByPointOfSaleAsync(pointOfSaleId, false))
            .ReturnsAsync(activeAssignments);

        // Act
        var act = () => _service.UnassignFromPointOfSaleAsync(pointOfSaleId, paymentMethod.Id);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*debe tener al menos un método de pago asignado*");
        _posPaymentMethodRepositoryMock.Verify(r => r.DeleteAsync(It.IsAny<Guid>()), Times.Never);
    }

    [Fact]
    public async Task UnassignFromPointOfSaleAsync_WhenAssignmentNotFound_ShouldThrowException()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethodId = Guid.NewGuid();

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethodId))
            .ReturnsAsync((PointOfSalePaymentMethod?)null);

        // Act
        var act = () => _service.UnassignFromPointOfSaleAsync(pointOfSaleId, paymentMethodId);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*Asignación de método de pago no encontrada*");
    }

    #endregion

    #region ChangeAssignmentStatusAsync Tests

    [Fact]
    public async Task ChangeAssignmentStatusAsync_DeactivateWhenMultipleActive_ShouldSucceed()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        var assignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethod.Id,
            IsActive = true,
            PaymentMethod = paymentMethod
        };

        var otherAssignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = Guid.NewGuid(),
            IsActive = true
        };

        var activeAssignments = new List<PointOfSalePaymentMethod> { assignment, otherAssignment };

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync(assignment);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetByPointOfSaleAsync(pointOfSaleId, false))
            .ReturnsAsync(activeAssignments);

        // Act
        var result = await _service.ChangeAssignmentStatusAsync(pointOfSaleId, paymentMethod.Id, false);

        // Assert
        result.Should().NotBeNull();
        result.IsActive.Should().BeFalse();
        _posPaymentMethodRepositoryMock.Verify(r => r.UpdateAsync(assignment), Times.Once);
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    [Fact]
    public async Task ChangeAssignmentStatusAsync_DeactivateLastActive_ShouldThrowException()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        var assignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethod.Id,
            IsActive = true,
            PaymentMethod = paymentMethod
        };

        var activeAssignments = new List<PointOfSalePaymentMethod> { assignment };

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync(assignment);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetByPointOfSaleAsync(pointOfSaleId, false))
            .ReturnsAsync(activeAssignments);

        // Act
        var act = () => _service.ChangeAssignmentStatusAsync(pointOfSaleId, paymentMethod.Id, false);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*debe tener al menos un método de pago activo*");
        _posPaymentMethodRepositoryMock.Verify(r => r.UpdateAsync(It.IsAny<PointOfSalePaymentMethod>()), Times.Never);
    }

    [Fact]
    public async Task ChangeAssignmentStatusAsync_ActivateInactive_ShouldSucceed()
    {
        // Arrange
        var pointOfSaleId = Guid.NewGuid();
        var paymentMethod = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        var assignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = paymentMethod.Id,
            IsActive = false,
            PaymentMethod = paymentMethod
        };

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, paymentMethod.Id))
            .ReturnsAsync(assignment);

        // Act
        var result = await _service.ChangeAssignmentStatusAsync(pointOfSaleId, paymentMethod.Id, true);

        // Assert
        result.Should().NotBeNull();
        result.IsActive.Should().BeTrue();
        _posPaymentMethodRepositoryMock.Verify(r => r.UpdateAsync(assignment), Times.Once);
        _unitOfWorkMock.Verify(u => u.SaveChangesAsync(), Times.Once);
    }

    #endregion

    #region Gift card payment method

    [Fact]
    public async Task GetByPointOfSaleAsync_ExcludeGiftCardFromSales_OmitsGiftCard()
    {
        var pointOfSaleId = Guid.NewGuid();
        var cash = TestDataGenerator.CreatePaymentMethod(code: "CASH", name: "Efectivo");
        var giftCard = TestDataGenerator.CreatePaymentMethod(
            code: GiftCardConstants.GiftCardPaymentMethodCode,
            name: "Tarjeta regalo");

        var assignments = new List<PointOfSalePaymentMethod>
        {
            new() { PointOfSaleId = pointOfSaleId, PaymentMethodId = cash.Id, IsActive = true, PaymentMethod = cash },
            new() { PointOfSaleId = pointOfSaleId, PaymentMethodId = giftCard.Id, IsActive = true, PaymentMethod = giftCard }
        };

        _pointOfSaleRepositoryMock.Setup(r => r.ExistsAsync(pointOfSaleId)).ReturnsAsync(true);
        _posPaymentMethodRepositoryMock.Setup(r => r.GetByPointOfSaleAsync(pointOfSaleId, false))
            .ReturnsAsync(assignments);

        var result = await _service.GetByPointOfSaleAsync(pointOfSaleId, false, excludeGiftCardFromSales: true);

        result.Should().HaveCount(1);
        result[0].PaymentMethod.Code.Should().Be("CASH");
    }

    [Fact]
    public async Task ChangeStatusAsync_DeactivateGiftCard_ThrowsDomainException()
    {
        var giftCard = TestDataGenerator.CreatePaymentMethod(
            code: GiftCardConstants.GiftCardPaymentMethodCode,
            name: "Tarjeta regalo");
        _paymentMethodRepositoryMock.Setup(r => r.GetByIdAsync(giftCard.Id)).ReturnsAsync(giftCard);

        var act = () => _service.ChangeStatusAsync(giftCard.Id, false);

        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*tarjeta regalo*");
    }

    [Fact]
    public async Task ChangeAssignmentStatusAsync_DeactivateGiftCard_ThrowsDomainException()
    {
        var pointOfSaleId = Guid.NewGuid();
        var giftCard = TestDataGenerator.CreatePaymentMethod(
            code: GiftCardConstants.GiftCardPaymentMethodCode,
            name: "Tarjeta regalo");
        var assignment = new PointOfSalePaymentMethod
        {
            Id = Guid.NewGuid(),
            PointOfSaleId = pointOfSaleId,
            PaymentMethodId = giftCard.Id,
            IsActive = true,
            PaymentMethod = giftCard
        };

        _posPaymentMethodRepositoryMock.Setup(r => r.GetAssignmentAsync(pointOfSaleId, giftCard.Id))
            .ReturnsAsync(assignment);

        var act = () => _service.ChangeAssignmentStatusAsync(pointOfSaleId, giftCard.Id, false);

        await act.Should().ThrowAsync<DomainException>()
            .WithMessage("*tarjeta regalo*");
    }

    #endregion
}
