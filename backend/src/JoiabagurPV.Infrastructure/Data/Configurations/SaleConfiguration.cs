using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

/// <summary>
/// EF Core configuration for Sale entity.
/// </summary>
public class SaleConfiguration : IEntityTypeConfiguration<Sale>
{
    public void Configure(EntityTypeBuilder<Sale> builder)
    {
        builder.ToTable("Sales");

        builder.HasKey(s => s.Id);

        builder.Property(s => s.ProductId)
            .IsRequired();

        builder.Property(s => s.PointOfSaleId)
            .IsRequired();

        builder.Property(s => s.UserId)
            .IsRequired();

        builder.Property(s => s.PaymentMethodId)
            .IsRequired();

        builder.Property(s => s.Price)
            .IsRequired()
            .HasPrecision(18, 2);

        builder.Property(s => s.Quantity)
            .IsRequired();

        builder.Property(s => s.PriceWasOverridden)
            .IsRequired()
            .HasDefaultValue(false);

        builder.Property(s => s.OriginalProductPrice)
            .HasPrecision(18, 2);

        builder.Property(s => s.Notes)
            .HasMaxLength(500);

        builder.Property(s => s.SaleDate)
            .IsRequired();

        builder.Property(s => s.CreatedAt)
            .IsRequired();

        builder.Property(s => s.UpdatedAt)
            .IsRequired();

        builder.Property(s => s.BulkOperationId);
        builder.HasIndex(s => s.BulkOperationId);

        // Indexes as defined in data model
        builder.HasIndex(s => new { s.PointOfSaleId, s.SaleDate });
        builder.HasIndex(s => new { s.ProductId, s.SaleDate });
        builder.HasIndex(s => new { s.UserId, s.SaleDate });
        builder.HasIndex(s => new { s.PaymentMethodId, s.SaleDate });

        // Relationships
        builder.HasOne(s => s.Product)
            .WithMany()
            .HasForeignKey(s => s.ProductId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(s => s.PointOfSale)
            .WithMany()
            .HasForeignKey(s => s.PointOfSaleId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(s => s.User)
            .WithMany()
            .HasForeignKey(s => s.UserId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(s => s.PaymentMethod)
            .WithMany()
            .HasForeignKey(s => s.PaymentMethodId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasOne(s => s.Photo)
            .WithOne(p => p.Sale)
            .HasForeignKey<SalePhoto>(p => p.SaleId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(s => s.InventoryMovement)
            .WithOne()
            .HasForeignKey<InventoryMovement>(m => m.SaleId)
            .OnDelete(DeleteBehavior.Restrict);

        // Attribution to the assisted search this sale came from. SetNull, and stated
        // explicitly: telemetry is expendable, so purging it must neither block nor destroy a
        // sale. Cascade here would mean deleting telemetry deletes sales; Restrict would make
        // any future retention policy impossible. EF also generates an index on the column,
        // which serves the event-to-sale direction and is meant to stay.
        builder.HasOne<ProductSearchEvent>()
            .WithMany()
            .HasForeignKey(s => s.SearchEventId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
