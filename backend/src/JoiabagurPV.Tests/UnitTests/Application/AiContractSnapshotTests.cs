using System.Reflection;
using System.Text.Json;
using FluentAssertions;
using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Tests.TestHelpers;

namespace JoiabagurPV.Tests.UnitTests.Application;

/// <summary>
/// The reciprocal of the Python snapshot test.
/// </summary>
/// <remarks>
/// jbg-ai already breaks its own build when the contract drifts. Without this, the .NET build
/// stays green and the drift surfaces at runtime as a silently null value — the worst possible
/// place to find out. With both guards in place, renegotiating the contract breaks both builds,
/// which is exactly what turns drift into an explicit conversation.
/// </remarks>
public class AiContractSnapshotTests
{
    private static readonly JsonSerializerOptions Wire = AiGatewaySerialization.Options;

    public static TheoryData<Type, string> ModelToSchema => new()
    {
        { typeof(AiSearchRequest), "RetrievalRequest" },
        { typeof(AiSearchFilters), "RetrievalFilters" },
        { typeof(AiSearchResult), "RetrievalResult" },
        { typeof(AiSearchResponse), "RetrievalResponse" },
        { typeof(AiDebugInfo), "DebugInfo" }
    };

    [Theory]
    [MemberData(nameof(ModelToSchema))]
    public void Dtos_MatchCommittedOpenApiSchema(Type model, string schemaName)
    {
        var schema = LoadSchema(schemaName);

        foreach (var property in model.GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            var wireName = Wire.PropertyNamingPolicy!.ConvertName(property.Name);

            schema.TryGetProperty(wireName, out var declared).Should().BeTrue(
                "{0}.{1} serializes as '{2}', which must exist in schema {3} of the committed contract",
                model.Name, property.Name, wireName, schemaName);

            IsNullableInContract(declared).Should().Be(
                IsNullableInModel(property),
                "nullability of '{0}' must match between {1} and schema {2}: the contract returns an " +
                "explicit null where a value is unknown, and a non-nullable member would hide that",
                wireName, model.Name, schemaName);
        }
    }

    /// <summary>
    /// The request model deliberately omits pos_id: the contract accepts it and ignores it,
    /// because scope comes from the token. Sending it would suggest the body carries authority.
    /// </summary>
    [Fact]
    public void SearchRequest_OmitsPosIdEvenThoughTheContractAcceptsIt()
    {
        LoadSchema("RetrievalRequest").TryGetProperty("pos_id", out _).Should().BeTrue(
            "the contract still declares it");

        typeof(AiSearchRequest).GetProperties()
            .Select(p => Wire.PropertyNamingPolicy!.ConvertName(p.Name))
            .Should().NotContain("pos_id");
    }

    private static JsonElement LoadSchema(string schemaName)
    {
        var path = RepositoryRoot.Resolve("ai-service", "openapi.json");

        File.Exists(path).Should().BeTrue("the committed contract must be readable at {0}", path);

        using var document = JsonDocument.Parse(File.ReadAllText(path));

        return document.RootElement
            .GetProperty("components")
            .GetProperty("schemas")
            .GetProperty(schemaName)
            .GetProperty("properties")
            .Clone();
    }

    /// <summary>
    /// Pydantic emits an optional field as anyOf[..., {"type": "null"}].
    /// </summary>
    private static bool IsNullableInContract(JsonElement property)
    {
        if (property.TryGetProperty("anyOf", out var anyOf))
        {
            return anyOf.EnumerateArray().Any(o =>
                o.TryGetProperty("type", out var t) && t.GetString() == "null");
        }

        return property.TryGetProperty("type", out var type) && type.GetString() == "null";
    }

    private static bool IsNullableInModel(PropertyInfo property)
    {
        var type = property.PropertyType;

        if (Nullable.GetUnderlyingType(type) is not null)
        {
            return true;
        }

        if (type.IsValueType)
        {
            return false;
        }

        return new NullabilityInfoContext().Create(property).WriteState == NullabilityState.Nullable;
    }
}
