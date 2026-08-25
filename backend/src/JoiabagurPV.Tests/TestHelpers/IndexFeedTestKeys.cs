namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// API key the integration host injects via <c>IndexFeed:ApiKey</c>. Distinct from the
/// local placeholder in <c>appsettings.json</c> and from the JWT secrets.
/// </summary>
public static class IndexFeedTestKeys
{
    public const string ApiKey = "test-index-feed-key-0123456789abcdef";

    public const string PreviousApiKey = "test-index-feed-prev-0123456789abcd";
}
