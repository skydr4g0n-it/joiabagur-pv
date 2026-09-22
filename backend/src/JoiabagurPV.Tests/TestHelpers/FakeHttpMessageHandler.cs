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
    private readonly Queue<Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>>> _responses = new();
    private readonly SemaphoreSlim _arrivals = new(0);
    private Func<HttpRequestMessage, HttpResponseMessage>? _fallback;

    /// <summary>How many requests reached this handler.</summary>
    public int RequestCount { get; private set; }

    /// <summary>Every request the handler saw, in order.</summary>
    public List<HttpRequestMessage> Requests { get; } = [];

    /// <summary>
    /// Bodies of the requests the handler saw, read when each one arrived — the content of a
    /// request message is disposed with it, so reading it after the call returns is too late.
    /// </summary>
    public List<string> RequestBodies { get; } = [];

    /// <summary>The most recent request, or null when none was issued.</summary>
    public HttpRequestMessage? LastRequest => Requests.Count == 0 ? null : Requests[^1];

    /// <summary>Queues one response with the given status and optional JSON body.</summary>
    public FakeHttpMessageHandler EnqueueResponse(HttpStatusCode statusCode, string? json = null)
    {
        _responses.Enqueue((_, _) => Task.FromResult(Build(statusCode, json)));
        return this;
    }

    /// <summary>Queues a transport-level failure whose cause is not known to precede the send.</summary>
    public FakeHttpMessageHandler EnqueueTransportFailure()
    {
        _responses.Enqueue((_, _) => throw new HttpRequestException("simulated transport failure"));
        return this;
    }

    /// <summary>
    /// Queues a failure to establish the connection: the one transport failure where the request
    /// is known not to have left, which the generative client is allowed to retry (C34).
    /// </summary>
    public FakeHttpMessageHandler EnqueueConnectionFailure()
    {
        _responses.Enqueue((_, _) => throw new HttpRequestException(
            HttpRequestError.ConnectionError, "simulated connection refused"));
        return this;
    }

    /// <summary>Queues a request that never completes until cancelled, to exercise the time budget.</summary>
    public FakeHttpMessageHandler EnqueueHang()
    {
        _responses.Enqueue((_, _) => throw new TaskCanceledException("simulated hang"));
        return this;
    }

    /// <summary>
    /// Queues a request that genuinely waits until the resilience pipeline cancels it.
    /// </summary>
    /// <remarks>
    /// <see cref="EnqueueHang"/> throws at once, so the pipeline never sees its own budget expire
    /// and never classifies the failure as a timeout — which is precisely the classification a
    /// retry predicate turns on. This one lets the timeout strategy fire for real, and pairs with
    /// a fake time provider so the test does not wait the budget out.
    /// </remarks>
    public FakeHttpMessageHandler EnqueueHangUntilCancelled()
    {
        _responses.Enqueue(async (_, cancellationToken) =>
        {
            await Task.Delay(Timeout.Infinite, cancellationToken);
            throw new InvalidOperationException("unreachable");
        });
        return this;
    }

    /// <summary>Answers every request not covered by the queue with this status.</summary>
    public FakeHttpMessageHandler AlwaysRespond(HttpStatusCode statusCode, string? json = null)
    {
        _fallback = _ => Build(statusCode, json);
        return this;
    }

    /// <summary>Completes once <paramref name="count"/> requests in total have reached the handler.</summary>
    public async Task WaitForRequestsAsync(int count, TimeSpan? timeout = null)
    {
        using var cts = new CancellationTokenSource(timeout ?? TimeSpan.FromSeconds(10));

        for (var seen = 0; seen < count; seen++)
        {
            await _arrivals.WaitAsync(cts.Token);
        }
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;
        Requests.Add(request);
        RequestBodies.Add(request.Content is null
            ? string.Empty
            : await request.Content.ReadAsStringAsync(cancellationToken));

        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> next;
        if (_responses.Count > 0)
        {
            next = _responses.Dequeue();
        }
        else if (_fallback is not null)
        {
            var fallback = _fallback;
            next = (r, _) => Task.FromResult(fallback(r));
        }
        else
        {
            throw new InvalidOperationException(
                $"FakeHttpMessageHandler received an unexpected request ({RequestCount}) with no queued response.");
        }

        _arrivals.Release();
        return await next(request, cancellationToken);
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
