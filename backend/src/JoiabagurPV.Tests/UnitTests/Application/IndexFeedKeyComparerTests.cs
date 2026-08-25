using FluentAssertions;
using JoiabagurPV.Application.Configuration;
using JoiabagurPV.Application.Services;
using JoiabagurPV.API.Filters;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Abstractions;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace JoiabagurPV.Tests.UnitTests.Application;

public class IndexFeedKeyComparerTests
{
    private const string Current = "current-index-feed-key-0123456789abcd";
    private const string Previous = "previous-index-feed-key-0123456789abc";

    [Fact]
    public void Matches_CurrentKey_IsTrue()
    {
        IndexFeedKeyComparer.Matches(Current, Current, previous: null).Should().BeTrue();
    }

    [Fact]
    public void Matches_PreviousKey_WhenConfigured_IsTrue()
    {
        IndexFeedKeyComparer.Matches(Previous, Current, Previous).Should().BeTrue();
    }

    [Fact]
    public void Matches_PreviousKey_WhenUnset_IsFalse()
    {
        IndexFeedKeyComparer.Matches(Previous, Current, previous: null).Should().BeFalse();
        IndexFeedKeyComparer.Matches(Previous, Current, previous: "").Should().BeFalse();
    }

    [Fact]
    public void Matches_Mismatch_IsFalse()
    {
        IndexFeedKeyComparer.Matches("wrong-index-feed-key-0123456789abcdef", Current, Previous)
            .Should().BeFalse();
    }

    [Fact]
    public void Matches_Absent_IsFalse()
    {
        IndexFeedKeyComparer.Matches(null, Current, Previous).Should().BeFalse();
        IndexFeedKeyComparer.Matches("", Current, Previous).Should().BeFalse();
    }

    [Fact]
    public void Matches_DifferentLength_IsFalseWithoutThrowing()
    {
        var act = () => IndexFeedKeyComparer.Matches("short", Current, Previous);
        act.Should().NotThrow();
        act().Should().BeFalse();
    }
}

public class IndexFeedKeyAttributeTests
{
    private const string Current = "current-index-feed-key-0123456789abcd";
    private const string Previous = "previous-index-feed-key-0123456789abc";

    [Fact]
    public async Task Filter_WithCurrentKey_CallsNext()
    {
        var (context, nextCalled, logs) = Arrange(Current, previous: Previous, header: Current);

        await new IndexFeedKeyAttribute().OnActionExecutionAsync(context, () =>
        {
            nextCalled.Value = true;
            return Task.FromResult<ActionExecutedContext>(null!);
        });

        nextCalled.Value.Should().BeTrue();
        context.Result.Should().BeNull();
        logs.Should().NotContain(line => line.Contains(Current));
    }

    [Fact]
    public async Task Filter_WithPreviousKey_CallsNext()
    {
        var (context, nextCalled, _) = Arrange(Current, previous: Previous, header: Previous);

        await new IndexFeedKeyAttribute().OnActionExecutionAsync(context, () =>
        {
            nextCalled.Value = true;
            return Task.FromResult<ActionExecutedContext>(null!);
        });

        nextCalled.Value.Should().BeTrue();
    }

    [Fact]
    public async Task Filter_WithMissingOrWrongKey_Returns401AndDoesNotLogTheHeader()
    {
        foreach (var header in new[] { (string?)null, "wrong-index-feed-key-0123456789abcdef" })
        {
            var (context, nextCalled, logs) = Arrange(Current, previous: Previous, header: header);

            await new IndexFeedKeyAttribute().OnActionExecutionAsync(context, () =>
            {
                nextCalled.Value = true;
                return Task.FromResult<ActionExecutedContext>(null!);
            });

            nextCalled.Value.Should().BeFalse();
            context.Result.Should().BeOfType<UnauthorizedResult>();
            if (header is not null)
            {
                logs.Should().NotContain(line => line.Contains(header));
            }

            logs.Should().NotContain(line => line.Contains(Current));
        }
    }

    private static (ActionExecutingContext Context, Box NextCalled, List<string> Logs) Arrange(
        string current,
        string? previous,
        string? header)
    {
        var logs = new List<string>();
        var services = new ServiceCollection();
        services.AddSingleton<IOptions<IndexFeedOptions>>(
            Options.Create(new IndexFeedOptions { ApiKey = current, ApiKeyPrevious = previous }));
        services.AddSingleton<ILoggerFactory>(new CapturingLoggerFactory(logs));
        var provider = services.BuildServiceProvider();

        var http = new DefaultHttpContext { RequestServices = provider };
        if (header is not null)
        {
            http.Request.Headers[IndexFeedOptions.HeaderName] = header;
        }

        var actionContext = new ActionContext(http, new RouteData(), new ActionDescriptor());
        var executing = new ActionExecutingContext(
            actionContext,
            new List<IFilterMetadata>(),
            new Dictionary<string, object?>(),
            controller: new object());

        return (executing, new Box(), logs);
    }

    private sealed class Box
    {
        public bool Value { get; set; }
    }

    private sealed class CapturingLoggerFactory(List<string> logs) : ILoggerFactory
    {
        public void AddProvider(ILoggerProvider provider)
        {
        }

        public ILogger CreateLogger(string categoryName) => new CapturingLogger(logs);

        public void Dispose()
        {
        }
    }

    private sealed class CapturingLogger(List<string> logs) : ILogger
    {
        public IDisposable BeginScope<TState>(TState state) where TState : notnull => NullScope.Instance;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            logs.Add(formatter(state, exception));
        }

        private sealed class NullScope : IDisposable
        {
            public static readonly NullScope Instance = new();

            public void Dispose()
            {
            }
        }
    }
}
