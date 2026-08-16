using System.Reflection;
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
            .Should().BeEmpty("the two static factories must be the only ways to build a scope");

        typeof(AiCallScope).IsValueType
            .Should().BeFalse("a value type would always have a default instance with an empty point of sale");
    }

    [Fact]
    public void ForCatalog_CarriesNoPointOfSale()
    {
        var scope = AiCallScope.ForCatalog(AnyUser, AnyRole);

        scope.PointOfSaleId.Should().BeNull(
            "enriching the catalog belongs to no point of sale, and a null cannot be mistaken "
            + "for one the way a sentinel value could");
        scope.Kind.Should().Be(AiCallScopeKind.Catalog);
        scope.UserId.Should().Be(AnyUser);
        scope.Role.Should().Be(AnyRole);
    }

    [Fact]
    public void ForCatalog_WhenRoleIsBlank_ThrowsArgumentException()
    {
        var act = () => AiCallScope.ForCatalog(AnyUser, "  ");

        act.Should().Throw<ArgumentException>()
            .WithParameterName("role");
    }

    [Fact]
    public void ForCatalog_WhenUserIsEmpty_ThrowsArgumentException()
    {
        var act = () => AiCallScope.ForCatalog(Guid.Empty, AnyRole);

        act.Should().Throw<ArgumentException>()
            .WithParameterName("userId");
    }

    [Fact]
    public void ForPointOfSale_IsMarkedAsPointOfSaleScoped()
    {
        var scope = AiCallScope.ForPointOfSale(AnyUser, AnyRole, AnyPointOfSale);

        scope.Kind.Should().Be(AiCallScopeKind.PointOfSale);
    }

    /// <summary>
    /// The catalog scope must remain a second scope, never a third construction path that
    /// happens to produce a point-of-sale one without a point of sale.
    /// </summary>
    [Fact]
    public void AiCallScope_ExposesExactlyTwoFactories()
    {
        typeof(AiCallScope)
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Where(method => method.ReturnType == typeof(AiCallScope))
            .Select(method => method.Name)
            .Should().BeEquivalentTo(["ForPointOfSale", "ForCatalog"]);
    }
}
