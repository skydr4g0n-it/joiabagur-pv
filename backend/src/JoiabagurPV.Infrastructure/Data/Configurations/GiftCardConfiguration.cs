using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

public class GiftCardConfiguration : IEntityTypeConfiguration<GiftCard>
{
    public void Configure(EntityTypeBuilder<GiftCard> builder)
    {
        builder.ToTable("GiftCards");

        builder.HasKey(g => g.Id);

        builder.Property(g => g.Code)
            .IsRequired()
            .HasMaxLength(16);

        builder.HasIndex(g => g.Code)
            .IsUnique();

        builder.Property(g => g.HolderName)
            .HasMaxLength(100);

        builder.Property(g => g.NominalAmount)
            .HasPrecision(18, 2);

        builder.Property(g => g.SpendableBalance)
            .HasPrecision(18, 2);

        builder.Property(g => g.ExpiryDate)
            .IsRequired();

        builder.Property(g => g.IssuanceIdempotencyKey)
            .HasMaxLength(128);

        builder.HasIndex(g => g.IssuanceIdempotencyKey)
            .IsUnique()
            .HasFilter("\"IssuanceIdempotencyKey\" IS NOT NULL");

        builder.HasIndex(g => g.PointOfSaleId);

        builder.HasOne(g => g.PointOfSale)
            .WithMany()
            .HasForeignKey(g => g.PointOfSaleId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(g => g.IssuanceSale)
            .WithMany()
            .HasForeignKey(g => g.IssuanceSaleId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(g => g.IssuedByUser)
            .WithMany()
            .HasForeignKey(g => g.IssuedByUserId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
