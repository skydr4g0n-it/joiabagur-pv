using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

public class PointOfSaleCommissionTierConfiguration : IEntityTypeConfiguration<PointOfSaleCommissionTier>
{
    public void Configure(EntityTypeBuilder<PointOfSaleCommissionTier> builder)
    {
        builder.ToTable("PointOfSaleCommissionTiers");

        builder.HasKey(t => t.Id);

        builder.Property(t => t.MinAmountInclusive)
            .HasColumnType("decimal(18,2)")
            .IsRequired();

        builder.Property(t => t.MaxAmountInclusive)
            .HasColumnType("decimal(18,2)");

        builder.Property(t => t.CommissionPercent)
            .HasColumnType("decimal(5,2)")
            .IsRequired();

        builder.HasIndex(t => t.PointOfSaleId);

        builder.HasOne(t => t.PointOfSale)
            .WithMany(pos => pos.CommissionTiers)
            .HasForeignKey(t => t.PointOfSaleId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
