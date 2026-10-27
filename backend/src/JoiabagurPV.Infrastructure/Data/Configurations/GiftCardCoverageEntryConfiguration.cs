using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

public class GiftCardCoverageEntryConfiguration : IEntityTypeConfiguration<GiftCardCoverageEntry>
{
    public void Configure(EntityTypeBuilder<GiftCardCoverageEntry> builder)
    {
        builder.ToTable("GiftCardCoverageEntries");

        builder.HasKey(e => e.Id);

        builder.Property(e => e.Amount)
            .HasPrecision(18, 2);

        builder.Property(e => e.EntryDate)
            .IsRequired();

        builder.HasIndex(e => new { e.GiftCardId, e.EntryDate });
        builder.HasIndex(e => e.SaleId);

        builder.HasOne(e => e.GiftCard)
            .WithMany(g => g.CoverageEntries)
            .HasForeignKey(e => e.GiftCardId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(e => e.Sale)
            .WithMany()
            .HasForeignKey(e => e.SaleId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
