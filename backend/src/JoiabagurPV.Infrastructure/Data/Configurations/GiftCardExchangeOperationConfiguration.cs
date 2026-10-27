using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

public class GiftCardExchangeOperationConfiguration : IEntityTypeConfiguration<GiftCardExchangeOperation>
{
    public void Configure(EntityTypeBuilder<GiftCardExchangeOperation> builder)
    {
        builder.ToTable("GiftCardExchangeOperations");

        builder.Property(e => e.IdempotencyKey)
            .HasMaxLength(128)
            .IsRequired();

        builder.Property(e => e.NewSaleIdsCsv)
            .HasMaxLength(2000)
            .IsRequired();

        builder.Property(e => e.ReturnIdsCsv)
            .HasMaxLength(2000)
            .IsRequired();

        builder.Property(e => e.CashDue)
            .HasPrecision(18, 2);

        builder.HasIndex(e => new { e.GiftCardId, e.IdempotencyKey })
            .IsUnique();

        builder.HasOne(e => e.GiftCard)
            .WithMany()
            .HasForeignKey(e => e.GiftCardId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
