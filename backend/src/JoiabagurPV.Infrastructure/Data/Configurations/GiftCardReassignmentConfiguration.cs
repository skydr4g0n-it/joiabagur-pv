using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

public class GiftCardReassignmentConfiguration : IEntityTypeConfiguration<GiftCardReassignment>
{
    public void Configure(EntityTypeBuilder<GiftCardReassignment> builder)
    {
        builder.ToTable("GiftCardReassignments");

        builder.HasKey(r => r.Id);

        builder.Property(r => r.OccurredAt)
            .IsRequired();

        builder.HasIndex(r => r.GiftCardId);

        builder.HasOne(r => r.GiftCard)
            .WithMany(g => g.Reassignments)
            .HasForeignKey(r => r.GiftCardId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(r => r.FromPointOfSale)
            .WithMany()
            .HasForeignKey(r => r.FromPointOfSaleId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(r => r.ToPointOfSale)
            .WithMany()
            .HasForeignKey(r => r.ToPointOfSaleId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(r => r.User)
            .WithMany()
            .HasForeignKey(r => r.UserId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
