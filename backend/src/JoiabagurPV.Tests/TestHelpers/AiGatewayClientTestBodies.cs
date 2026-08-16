namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// Wire bodies shared between the retrieval and enrichment gateway suites.
/// </summary>
/// <remarks>
/// Exists for exactly one test: the one that drives the enrichment circuit open and then proves
/// retrieval still answers. That test needs a valid retrieval body while living in the
/// enrichment suite, and duplicating the JSON would leave two copies of a contract shape to keep
/// in step by hand.
/// </remarks>
public static class AiGatewayClientTestBodies
{
    /// <summary>A minimal, valid retrieval response.</summary>
    public const string RetrievalSuccess = """
        {
          "results": [
            {
              "product_id": "11111111-1111-1111-1111-111111111111",
              "sku": "ERIZO-M",
              "score": 0.87,
              "match_reasons": ["material"],
              "materials": ["plata"],
              "family_id": null,
              "variant_label": null,
              "debug": null
            }
          ],
          "candidates_returned": 1,
          "low_confidence": false,
          "trace_id": "trace-test-0001",
          "effective_pos_id": "44444444-4444-4444-4444-444444444444"
        }
        """;
}
