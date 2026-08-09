using System.Net;

namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// Programmable HTTP handler for outbound-client tests: no network, no container, no service.
/// </summary>
/// <remarks>
/// Counts the requests actually issued, which is what most of the gateway tests assert on.
/// Whether a permanent condition was retried is invisible in the exception type — a predicate
/// that retries everything still throws the right exception, just later and after burning the
/// time budget. The request count is the only thing that tells the two apart.
///
/// Introduced by C03 and meant to be reused by C12, C15 and C34.
/// </remarks>
public class FakeHttpMessageHandler : HttpMessageHandler
{
    private readonly Queue<Func<HttpRequestMessage, HttpResponseMessage>> _responses = new();
    private Func<HttpRequestMessage, HttpResponseMessage>? _fallback;

    /// <summary>How many requests reached this handler.</summary>
    public int RequestCount { get; private set; }

    /// <summary>Every request the handler saw, in order.</summary>
    public List<HttpRequestMessage> Requests { get; } = [];

    /// <summary>The most recent request, or null when none was issued.</summary>
    public HttpRequestMessage? LastRequest => Requests.Count == 0 ? null : Requests[^1];

    /// <summary>Queues one response with the given status and optional JSON body.</summary>
    public FakeHttpMessageHandler EnqueueResponse(HttpStatusCode statusCode, string? json = null)
    {
        _responses.Enqueue(_ => Build(statusCode, json));
        return this;
    }

    /// <summary>Queues a transport-level failure.</summary>
    public FakeHttpMessageHandler EnqueueTransportFailure()
    {
        _responses.Enqueue(_ => throw new HttpRequestException("simulated transport failure"));
        return this;
    }

    /// <summary>Queues a request that never completes until cancelled, to exercise the time budget.</summary>
    public FakeHttpMessageHandler EnqueueHang()
    {
        _responses.Enqueue(_ => throw new TaskCanceledException("simulated hang"));
        return this;
    }

    /// <summary>Answers every request not covered by the queue with this status.</summary>
    public FakeHttpMessageHandler AlwaysRespond(HttpStatusCode statusCode, string? json = null)
    {
        _fallback = _ => Build(statusCode, json);
        return this;
    }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;
        Requests.Add(request);

        var next = _responses.Count > 0
            ? _responses.Dequeue()
            : _fallback ?? throw new InvalidOperationException(
                $"FakeHttpMessageHandler received an unexpected request ({RequestCount}) with no queued response.");

        return Task.FromResult(next(request));
    }

    private static HttpResponseMessage Build(HttpStatusCode statusCode, string? json)
    {
        var response = new HttpResponseMessage(statusCode);

        if (json is not null)
        {
            response.Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
        }

        return response;
    }
}
