using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

/// <summary>
/// Entity Framework configuration for the FamilyReviewVerdict entity.
/// </summary>
/// <remarks>
/// Everything declared here defends something whose absence produces no error: a duplicate pair
/// that turns one judgement into two, a delete rule that leaves verdicts pointing at a family that
/// is gone, and an enum stored as a native PostgreSQL type that survives its own table.
/// </remarks>
public class FamilyReviewVerdictConfiguration : IEntityTypeConfiguration<FamilyReviewVerdict>
{
    public void Configure(EntityTypeBuilder<FamilyReviewVerdict> builder)
    {
        builder.ToTable("FamilyReviewVerdicts");

        builder.HasKey(e => e.Id);

        builder.Property(e => e.ProductId).IsRequired();
        builder.Property(e => e.ProductFamilyId).IsRequired();

        // Stored as an int, never as a native PostgreSQL enum type — the same reasoning
        // ProductFamily.Origin records: an enum type survives its table being dropped, so a
        // rollback leaves an orphan that makes a later migration fail with "type already exists",
        // weeks later and with no obvious connection to this change.
        builder.Property(e => e.Outcome)
            .IsRequired()
            .HasConversion<int>();

        builder.Property(e => e.ReviewedByUserId).IsRequired();
        builder.Property(e => e.ReviewedAt).IsRequired();
        builder.Property(e => e.MarginAtReview);
        builder.Property(e => e.Note).HasMaxLength(FamilyReviewVerdict.NoteMaxLength);

        // The pair is the identity of a judgement, so judging it twice is a correction and not a
        // second opinion. Without this a reviewer who changes their mind leaves two contradictory
        // rows and the audit filter starts depending on which one it happens to read.
        builder.HasIndex(e => new { e.ProductId, e.ProductFamilyId }).IsUnique();

        // Cascade from the family: a judgement about a family that no longer exists answers a
        // question nobody can ask. Declared through the navigation so the delete rule travels with
        // the relationship rather than being left at the framework default.
        builder.HasOne(e => e.Family)
            .WithMany()
            .HasForeignKey(e => e.ProductFamilyId)
            .OnDelete(DeleteBehavior.Cascade);

        // Restrict towards the product, not cascade. A product is deactivated rather than deleted
        // in this catalog, but if one ever is, losing the record of what a person decided about it
        // would be silent and unrecoverable.
        builder.HasOne<Product>()
            .WithMany()
            .HasForeignKey(e => e.ProductId)
            .OnDelete(DeleteBehavior.Restrict);

        // Restrict towards the reviewer, for the reason ProductFamily.ApprovedByUserId already
        // records: deleting a user must not destroy the evidence of the reviews they performed,
        // which is the very figure the delivery checklist asks this change to produce.
        builder.HasOne<User>()
            .WithMany()
            .HasForeignKey(e => e.ReviewedByUserId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
