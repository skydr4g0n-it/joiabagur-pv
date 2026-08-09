namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// Locates the repository root from the test assembly location, so a test can read artefacts
/// that live outside the backend — such as the frozen contract of the AI service.
/// </summary>
/// <remarks>
/// The .NET counterpart of the path helper the Python test suite already uses.
/// </remarks>
public static class RepositoryRoot
{
    private const string Marker = "openspec";

    /// <summary>Absolute path of the repository root.</summary>
    public static string Find()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null)
        {
            if (Directory.Exists(Path.Combine(directory.FullName, Marker)))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException(
            $"Could not locate the repository root: no ancestor of '{AppContext.BaseDirectory}' contains a '{Marker}' directory.");
    }

    /// <summary>Resolves a path relative to the repository root.</summary>
    public static string Resolve(params string[] segments) =>
        Path.Combine([Find(), .. segments]);
}
