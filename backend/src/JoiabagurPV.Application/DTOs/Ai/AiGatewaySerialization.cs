using System.Text.Json;
using System.Text.Json.Serialization;

namespace JoiabagurPV.Application.DTOs.Ai;

/// <summary>
/// Single serialization contract for every exchange with jbg-ai.
/// </summary>
/// <remarks>
/// The wire format is <c>snake_case</c>, frozen by the Python side. Applying it once as a
/// naming policy keeps the models free of per-property attributes: an attribute per field
/// is thirty chances to mistype a name the compiler cannot check, and the mistake would
/// surface as a silently null value rather than as an error.
/// </remarks>
public static class AiGatewaySerialization
{
    /// <summary>Options used for both request serialization and response deserialization.</summary>
    public static readonly JsonSerializerOptions Options = Create();

    private static JsonSerializerOptions Create()
    {
        var options = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            PropertyNameCaseInsensitive = false,
            DefaultIgnoreCondition = JsonIgnoreCondition.Never
        };

        // Retrieval mode travels as the lowercase string the contract declares.
        options.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower));

        return options;
    }
}
