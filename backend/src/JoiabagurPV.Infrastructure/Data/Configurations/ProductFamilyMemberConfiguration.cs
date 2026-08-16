using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

/// <summary>
/// Entity Framework configuration for the ProductFamilyMember entity.
/// </summary>
/// <remarks>
/// Three unique indexes, and each one defends an invariant that is wrong <em>without producing any
/// error</em>: a product in two families, two siblings sharing a position, two siblings sharing a
/// label. All three save happily and are discovered downstream, once there is data to lose.
/// </remarks>
public class ProductFamilyMemberConfiguration : IEntityTypeConfiguration<ProductFamilyMember>
{
    public void Configure(EntityTypeBuilder<ProductFamilyMember> builder)
    {
        builder.ToTable("ProductFamilyMembers");

        builder.HasKey(e => e.Id);

        builder.Property(e => e.ProductFamilyId)
            .IsRequired();

        builder.Property(e => e.ProductId)
            .IsRequired();

        // Bound taken from the entity, not restated here: the request validators enforce the same
        // number and cannot see this project.
        builder.Property(e => e.VariantLabel)
            .HasMaxLength(ProductFamilyMember.VariantLabelMaxLength);

        builder.Property(e => e.SortOrder)
            .IsRequired();

        // A product belongs to at most one family, enforced by the database. An application check
        // would leave a race open between two administrators and, worse, a second membership
        // produces no error anywhere: it would surface as two family identifiers emitted for one
        // product and as duplicated documents in the vector index.
        builder.HasIndex(e => e.ProductId)
            .IsUnique();

        // Order is unique within the family. Two members sharing a position still save, still read
        // back, and simply return the siblings in an order that differs between reads — which in a
        // disambiguation screen is worse than having no order at all.
        builder.HasIndex(e => new { e.ProductFamilyId, e.SortOrder })
            .IsUnique();

        // So is the label. Two members labelled "M" in one family defeat the entire point of the
        // family. Nulls do not collide with each other in PostgreSQL, so this single index also
        // allows any number of members whose variant has not been determined yet — which is a
        // legitimate state, not a defect.
        builder.HasIndex(e => new { e.ProductFamilyId, e.VariantLabel })
            .IsUnique();

        // Cursor for the indexing feed, same reasoning as the family's.
        builder.HasIndex(e => e.UpdatedAt);

        // Restrict, not the framework default. A required relationship defaults to Cascade, which
        // here would mean that deleting a product silently destroys the curation done on it — and a
        // product is retired with IsActive anyway, so a real delete is already the exceptional path.
        // The relationship towards the family is declared from the family side, as a cascade.
        builder.HasOne<Product>()
            .WithMany()
            .HasForeignKey(e => e.ProductId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
