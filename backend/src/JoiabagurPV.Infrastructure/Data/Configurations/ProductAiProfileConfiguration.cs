using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

/// <summary>
/// Entity Framework configuration for the ProductAiProfile entity.
/// </summary>
/// <remarks>
/// Everything declared by hand here shares one property: getting it wrong produces no error at
/// all. A JSON column silently landing as <c>text</c>, an index that exists but is not unique, a
/// delete rule left at the framework default — none of them break a build, fail a save or show
/// up in a log. They surface weeks later, with data already in the table, which is exactly too
/// late. The schema assertions in the test project exist to hold them.
/// </remarks>
public class ProductAiProfileConfiguration : IEntityTypeConfiguration<ProductAiProfile>
{
    /// <summary>
    /// Maximum length of the short vocabulary columns. Generous on purpose: the closed
    /// vocabularies for piece type, stone and size are decided by the enrichment pipeline, not
    /// here, and a bound that is too tight would reject a legitimate value with a database error.
    /// </summary>
    public const int VocabularyMaxLength = 64;

    /// <summary>Length of a hexadecimal SHA-256 digest.</summary>
    public const int SourceHashLength = 64;

    public void Configure(EntityTypeBuilder<ProductAiProfile> builder)
    {
        builder.ToTable("ProductAiProfiles");

        builder.HasKey(e => e.Id);

        builder.Property(e => e.ProductId)
            .IsRequired();

        // Vocabularies as text, never a PostgreSQL enum type. Two reasons, and the second is the
        // expensive one: the vocabularies are closed by the enrichment pipeline in a later
        // change, and an enum type survives its table being dropped, so a rollback leaves an
        // orphan type that makes the next migration fail with "type already exists" weeks later.
        builder.Property(e => e.PieceType)
            .HasMaxLength(VocabularyMaxLength);

        builder.Property(e => e.StoneType)
            .HasMaxLength(VocabularyMaxLength);

        builder.Property(e => e.SizeLabel)
            .HasMaxLength(VocabularyMaxLength);

        // jsonb rather than text, for all seven documents. These columns exist to be queried and
        // aggregated in SQL — the correction rate per field is a comparison between two of them —
        // and jsonb also makes an invalid document impossible to store by construction.
        builder.Property(e => e.MaterialsJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.ColorTagsJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.StyleTagsJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.OccasionTagsJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.FieldConfidenceJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.FieldSourceJson)
            .IsRequired()
            .HasColumnType("jsonb");

        builder.Property(e => e.ProposedProfileJson)
            .IsRequired()
            .HasColumnType("jsonb");

        // Precision stated explicitly: the default for decimal on Npgsql is unbounded numeric,
        // which stores a confidence of 0.7200000000000001 as faithfully as 0.72 and makes any
        // equality assertion on it a coin toss.
        builder.Property(e => e.AiConfidence)
            .IsRequired()
            .HasPrecision(4, 3);

        builder.Property(e => e.GeneratedByModel)
            .HasMaxLength(128);

        builder.Property(e => e.PromptVersion)
            .HasMaxLength(32);

        builder.Property(e => e.SourceHash)
            .IsRequired()
            .HasMaxLength(SourceHashLength);

        builder.Property(e => e.ReviewStatus)
            .IsRequired()
            .HasConversion<int>();

        builder.Property(e => e.ReviewOrigin)
            .IsRequired()
            .HasConversion<int>();

        builder.Property(e => e.ReviewedByUserId);
        builder.Property(e => e.ReviewedAt);
        builder.Property(e => e.ReviewDurationMs);

        // One profile per product, enforced by the database. An application check would leave a
        // race open, and — worse — a second profile produces no error anywhere: it would be
        // discovered as duplicated documents in the vector index, long after the fact.
        builder.HasIndex(e => e.ProductId)
            .IsUnique();

        // Two query indexes. Neither improves anything measurable at the volume this table will
        // ever see; they exist because adding one later costs a migration slot out of the six the
        // plan allows, and having them costs nothing. Status first in the composite: it is the
        // equality predicate of both queries, and the reverse order would serve neither.
        builder.HasIndex(e => e.ReviewStatus);
        builder.HasIndex(e => new { e.ReviewStatus, e.ReviewOrigin });

        // Both delete behaviours stated explicitly. The framework default for a required
        // relationship is Cascade, which here would mean "deleting a product deletes the record
        // of the review work done on it" — and a product is retired with IsActive anyway, so a
        // real delete is already the exceptional path.
        builder.HasOne<Product>()
            .WithMany()
            .HasForeignKey(e => e.ProductId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne<User>()
            .WithMany()
            .HasForeignKey(e => e.ReviewedByUserId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
