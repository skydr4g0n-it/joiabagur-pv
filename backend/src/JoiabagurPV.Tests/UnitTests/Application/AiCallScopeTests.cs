using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The scope is the guard that stops a sentinel point of sale from ever reaching the
/// retriever's hard filter. These tests pin that guard.
/// </summary>
public class AiCallScopeTests
{
    private static readonly Guid AnyUser = Guid.NewGuid();
    private static readonly Guid AnyPointOfSale = Guid.NewGuid();
    private const string AnyRole = "Operator";

    [Fact]
    public void ForPointOfSale_WithValidArguments_BuildsScope()
    {
        var scope = AiCallScope.ForPointOfSale(AnyUser, AnyRole, AnyPointOfSale);

        scope.UserId.Should().Be(AnyUser);
        scope.Role.Should().Be(AnyRole);
        scope.PointOfSaleId.Should().Be(AnyPointOfSale);
    }

    [Fact]
    public void ForPointOfSale_WhenPointOfSaleIsEmpty_ThrowsArgumentException()
    {
        var act = () => AiCallScope.ForPointOfSale(AnyUser, AnyRole, Guid.Empty);

        act.Should().Throw<ArgumentException>()
            .WithParameterName("pointOfSaleId");
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void ForPointOfSale_WhenRoleIsBlank_ThrowsArgumentException(string role)
    {
        var act = () => AiCallScope.ForPointOfSale(AnyUser, role, AnyPointOfSale);

        act.Should().Throw<ArgumentException>()
            .WithParameterName("role");
    }

    [Fact]
    public void ForPointOfSale_WhenUserIsEmpty_ThrowsArgumentException()
    {
        var act = () => AiCallScope.ForPointOfSale(Guid.Empty, AnyRole, AnyPointOfSale);

        act.Should().Throw<ArgumentException>()
            .WithParameterName("userId");
    }

    /// <summary>
    /// Guards the reason the type is a sealed class and not a record struct: a struct would
    /// always have a `default` value carrying an empty point of sale, which is exactly the
    /// state the factory exists to prevent.
    /// </summary>
    [Fact]
    public void AiCallScope_ExposesNoPublicConstructor()
    {
        typeof(AiCallScope)
            .GetConstructors()
            .Should().BeEmpty("ForPointOfSale must be the only way to build a scope");

        typeof(AiCallScope).IsValueType
            .Should().BeFalse("a value type would always have a default instance with an empty point of sale");
    }
}
