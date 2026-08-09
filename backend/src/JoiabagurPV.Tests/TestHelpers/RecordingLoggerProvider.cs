using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>One captured log event, with its template, named properties and active scopes.</summary>
public sealed record CapturedLogEntry(
    LogLevel Level,
    string Template,
    string Message,
    IReadOnlyDictionary<string, object?> Properties,
    IReadOnlyList<object?> Scopes)
{
    /// <summary>Value of a named property of the message template, or null when absent.</summary>
    public object? Property(string name) => Properties.TryGetValue(name, out var value) ? value : null;

    /// <summary>Value bound under <paramref name="key"/> by any active <c>BeginScope</c>.</summary>
    public object? ScopeValue(string key)
    {
        foreach (var scope in Scopes)
        {
            if (scope is IEnumerable<KeyValuePair<string, object>> pairs)
            {
                foreach (var pair in pairs)
                {
                    if (pair.Key == key)
                    {
                        return pair.Value;
                    }
                }
            }
        }

        return null;
    }

    /// <summary>Whether <paramref name="text"/> appears anywhere in the event or its properties.</summary>
    public bool Mentions(string text) =>
        Message.Contains(text, StringComparison.Ordinal)
        || Properties.Values.Any(v => v?.ToString()?.Contains(text, StringComparison.Ordinal) == true);
}

/// <summary>
/// Captures structured log events so a test can assert on them.
/// </summary>
/// <remarks>
/// Structured logging is a requirement here, not decoration: the events are what answer "how long
/// did it take", "how many attempts" and "where was it pointing" when a call misbehaves, and one of
/// them carries a privacy rule — the operator's query must never rise above debug level. A rule
/// nothing asserts is a rule one refactor away from being gone.
///
/// Introduced by C03 and meant to be reused wherever an outbound call must be observable.
/// </remarks>
public sealed class RecordingLoggerProvider : ILoggerProvider
{
    private readonly List<CapturedLogEntry> _entries = [];
    private readonly AsyncLocal<IReadOnlyList<object?>> _scopes = new();

    /// <summary>Everything captured so far, oldest first.</summary>
    public IReadOnlyList<CapturedLogEntry> Entries
    {
        get { lock (_entries) { return [.. _entries]; } }
    }

    /// <summary>Entries emitted at the given level.</summary>
    public IEnumerable<CapturedLogEntry> At(LogLevel level) => Entries.Where(e => e.Level == level);

    /// <summary>The single entry whose template starts with <paramref name="template"/>.</summary>
    public CapturedLogEntry Single(string template) =>
        Entries.Single(e => e.Template.StartsWith(template, StringComparison.Ordinal));

    /// <summary>Whether any entry used the given template.</summary>
    public bool Has(string template) =>
        Entries.Any(e => e.Template.StartsWith(template, StringComparison.Ordinal));

    public ILogger CreateLogger(string categoryName) => new RecordingLogger(this);

    public void Dispose() { }

    private void Record(CapturedLogEntry entry)
    {
        lock (_entries) { _entries.Add(entry); }
    }

    private IDisposable PushScope(object? state)
    {
        var previous = _scopes.Value ?? [];
        _scopes.Value = [.. previous, state];
        return new ScopeHandle(this, previous);
    }

    private sealed class ScopeHandle(RecordingLoggerProvider provider, IReadOnlyList<object?> previous) : IDisposable
    {
        public void Dispose() => provider._scopes.Value = previous;
    }

    private sealed class RecordingLogger(RecordingLoggerProvider provider) : ILogger
    {
        public IDisposable BeginScope<TState>(TState state) where TState : notnull =>
            provider.PushScope(state);

        public bool IsEnabled(LogLevel logLevel) => logLevel != LogLevel.None;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            var properties = new Dictionary<string, object?>(StringComparer.Ordinal);
            var template = string.Empty;

            if (state is IReadOnlyList<KeyValuePair<string, object?>> values)
            {
                foreach (var pair in values)
                {
                    if (pair.Key == "{OriginalFormat}")
                    {
                        template = pair.Value?.ToString() ?? string.Empty;
                    }
                    else
                    {
                        properties[pair.Key] = pair.Value;
                    }
                }
            }

            provider.Record(new CapturedLogEntry(
                logLevel,
                template,
                formatter(state, exception),
                properties,
                provider._scopes.Value ?? []));
        }
    }
}
