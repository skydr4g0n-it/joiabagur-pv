using Npgsql;

namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// Reads the shape a migration actually produced, straight from the PostgreSQL catalog.
/// </summary>
/// <remarks>
/// A test that only asserts "the migration applies" is theatre: <see cref="IntegrationTests.TestDatabaseFixture"/>
/// already migrates before every integration test. The value is entirely in the properties
/// that are wrong <em>without producing any error</em> — a column that silently lands as
/// <c>text</c> instead of <c>jsonb</c>, a composite index whose columns ended up reversed, a
/// delete rule left at the framework default. Those surface weeks later, with data already in
/// the table, which is exactly too late.
///
/// This helper is shared on purpose: five more migrations are planned (C07, C08, C19, C27,
/// C29) and each should be able to assert its own schema in a handful of lines. It holds only
/// the questions the current change needs — the next one extends it when it knows what it
/// needs, rather than guessing now.
/// </remarks>
public sealed class SchemaAssert : IAsyncDisposable
{
    private readonly NpgsqlConnection _connection;

    private SchemaAssert(NpgsqlConnection connection) => _connection = connection;

    /// <summary>
    /// Opens a reader over an already migrated database.
    /// </summary>
    public static async Task<SchemaAssert> OpenAsync(string connectionString)
    {
        var connection = new NpgsqlConnection(connectionString);
        await connection.OpenAsync();
        return new SchemaAssert(connection);
    }

    /// <summary>
    /// The declared SQL type of a column, as the catalog reports it — for example <c>jsonb</c>,
    /// <c>character varying</c> or <c>integer</c>. Null when the column does not exist.
    /// </summary>
    public async Task<string?> ColumnTypeAsync(string table, string column) =>
        await ScalarAsync<string>(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = @table AND column_name = @column
            """,
            ("table", table), ("column", column));

    /// <summary>
    /// Whether a column accepts nulls. Null when the column does not exist.
    /// </summary>
    public async Task<bool?> ColumnIsNullableAsync(string table, string column)
    {
        var value = await ScalarAsync<string>(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = @table AND column_name = @column
            """,
            ("table", table), ("column", column));

        return value is null ? null : value == "YES";
    }

    /// <summary>
    /// The maximum length of a character column, or null when it is unbounded or absent.
    /// </summary>
    public async Task<int?> ColumnMaxLengthAsync(string table, string column) =>
        await ScalarAsync<int?>(
            """
            SELECT character_maximum_length FROM information_schema.columns
            WHERE table_name = @table AND column_name = @column
            """,
            ("table", table), ("column", column));

    /// <summary>
    /// The columns of an index, <strong>in index order</strong>. Empty when the index does not exist.
    /// </summary>
    /// <remarks>
    /// Order is the whole point. A composite index whose columns are declared the wrong way
    /// round still exists, still reports as present, and simply fails to serve the query it was
    /// created for — without ever raising an error.
    /// </remarks>
    public async Task<IReadOnlyList<string>> IndexColumnsAsync(string indexName)
    {
        var columns = new List<string>();

        await using var command = new NpgsqlCommand(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            CROSS JOIN LATERAL unnest(i.indkey::smallint[]) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
            WHERE c.relname = @index
            ORDER BY k.ord
            """,
            _connection);
        command.Parameters.AddWithValue("index", indexName);

        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            columns.Add(reader.GetString(0));
        }

        return columns;
    }

    /// <summary>
    /// Whether an index enforces uniqueness. Null when the index does not exist.
    /// </summary>
    /// <remarks>
    /// Added by the change that introduces the AI profile, where "one profile per product" is an
    /// invariant nothing else defends. A non-unique index is indistinguishable from a unique one
    /// in every symptom available before the damage: it exists, it is reported as present, it
    /// serves the same queries, and the second row saves without complaint. It surfaces later as
    /// duplicated documents in the vector index, with no way left to tell which profile is the
    /// real one.
    /// </remarks>
    public async Task<bool?> IndexIsUniqueAsync(string indexName)
    {
        var value = await ScalarAsync<bool?>(
            """
            SELECT i.indisunique
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            WHERE c.relname = @index
            """,
            ("index", indexName));

        return value;
    }

    /// <summary>
    /// The delete rule of a foreign key — <c>CASCADE</c>, <c>RESTRICT</c>, <c>SET NULL</c> or
    /// <c>NO ACTION</c>. Null when the constraint does not exist.
    /// </summary>
    public async Task<string?> ForeignKeyDeleteRuleAsync(string constraintName) =>
        await ScalarAsync<string>(
            """
            SELECT delete_rule FROM information_schema.referential_constraints
            WHERE constraint_name = @name
            """,
            ("name", constraintName));

    private async Task<T?> ScalarAsync<T>(string sql, params (string Name, object Value)[] parameters)
    {
        await using var command = new NpgsqlCommand(sql, _connection);
        foreach (var (name, value) in parameters)
        {
            command.Parameters.AddWithValue(name, value);
        }

        var result = await command.ExecuteScalarAsync();
        return result is null or DBNull ? default : (T)result;
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync() => await _connection.DisposeAsync();
}
