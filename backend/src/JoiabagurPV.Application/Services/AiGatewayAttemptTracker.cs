namespace JoiabagurPV.Application.Services;

/// <summary>
/// Counts how many HTTP attempts a single gateway call actually consumed.
/// </summary>
/// <remarks>
/// The retry lives inside the resilience pipeline, below the client, so the number of attempts
/// is not observable from the call site. An ambient counter, started by the client and bumped by
/// the pipeline's retry callback, closes that gap: the retry callback runs inside the same async
/// flow, and the shared box makes the increment visible again when the call returns.
///
/// This exists because "how many times did we try" is one of the first questions asked when a
/// call is slow, and a log line that cannot answer it is close to useless.
/// </remarks>
public static class AiGatewayAttemptTracker
{
    private sealed class Counter
    {
        public int Attempts;
    }

    private static readonly AsyncLocal<Counter?> Current = new();

    /// <summary>Starts counting for the call about to be issued. One attempt is assumed.</summary>
    public static void Begin() => Current.Value = new Counter { Attempts = 1 };

    /// <summary>Records one further attempt. Called from the resilience pipeline's retry hook.</summary>
    public static void RecordRetry()
    {
        var counter = Current.Value;
        if (counter is not null)
        {
            counter.Attempts++;
        }
    }

    /// <summary>Attempts consumed so far, or zero when no call is in flight.</summary>
    public static int Attempts => Current.Value?.Attempts ?? 0;

    /// <summary>Clears the ambient counter at the end of a call.</summary>
    public static void End() => Current.Value = null;
}
