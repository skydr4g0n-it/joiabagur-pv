using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

/// <summary>
/// Entity Framework configuration for the ProductSearchEvent entity.
/// </summary>
/// <remarks>
/// Three things here are declared by hand precisely because getting them wrong produces no
/// error at all, and the mistake only surfaces weeks later with data already in the table:
/// the <c>jsonb</c> column type, the column order of the composite index, and every delete
/// behaviour. The schema assertions in the test project exist to hold them.
/// </remarks>
public class ProductSearchEventConfiguration : IEntityTypeConfiguration<ProductSearchEvent>
{
    /// <summary>
    /// Maximum length of the query text, taken from <c>query.maxLength</c> in the frozen
    /// <c>ai-service/openapi.json</c> contract rather than picked by eye. If the contract ever
    /// widens it, the mismatch belongs in the review of that renegotiation.
    /// </summary>
    public const int SearchTextMaxLength = 500;

    public void Configure(EntityTypeBuilder<ProductSearchEvent> builder)
    {
        builder.ToTable("ProductSearchEvents");

        builder.HasKey(e => e.Id);

        builder.Property(e => e.UserId)
            .IsRequired();

        builder.Property(e => e.PointOfSaleId)
            .IsRequired();

        builder.Property(e => e.SearchSessionId)
            .IsRequired();

        builder.Property(e => e.SearchText)
            .IsRequired()
            .HasMaxLength(SearchTextMaxLength);

        // jsonb rather than text: this column exists to be aggregated, not stashed. It also
        // makes the byte-truncation bug impossible by construction, because PostgreSQL rejects
        // a document that is no longer valid JSON.
        builder.Property(e => e.FiltersJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.ResultsJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.ResultsCount)
            .IsRequired();

        builder.Property(e => e.SearchOrigin)
            .IsRequired()
            .HasConversion<int>();

        builder.Property(e => e.TraceId)
            .HasMaxLength(64);

        builder.Property(e => e.RetrievalMs);
        builder.Property(e => e.TotalMs);

        builder.Property(e => e.SelectedProductId);
        builder.Property(e => e.SelectedFromRank);
        builder.Property(e => e.SelectedAt);

        // Two indexes, and no more. At the volume this table will ever see, none of them
        // improves anything measurable; they exist because adding one later costs a migration
        // slot out of the six the plan allows, and having them costs nothing.
        // Point of sale first: it is the equality predicate of the dominant query, and the
        // reverse order would not serve it.
        builder.HasIndex(e => new { e.PointOfSaleId, e.CreatedAt });
        builder.HasIndex(e => e.CreatedAt);

        // Every delete behaviour is stated explicitly. The framework default for a required
        // relationship is Cascade, which here would mean "deleting an employee deletes the
        // evidence of how the system was used".
        builder.HasOne<User>()
            .WithMany()
            .HasForeignKey(e => e.UserId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne<PointOfSale>()
            .WithMany()
            .HasForeignKey(e => e.PointOfSaleId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne<Product>()
            .WithMany()
            .HasForeignKey(e => e.SelectedProductId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
