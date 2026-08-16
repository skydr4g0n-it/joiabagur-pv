using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace JoiabagurPV.Infrastructure.Data.Configurations;

/// <summary>
/// Entity Framework configuration for the ProductFamily entity.
/// </summary>
/// <remarks>
/// The declarations here that matter are the ones whose absence produces no error: an enum stored
/// as a native PostgreSQL type, a delete rule left at the framework default, and an index missing
/// for a cursor that does not exist yet. None of them break a build or fail a save.
/// </remarks>
public class ProductFamilyConfiguration : IEntityTypeConfiguration<ProductFamily>
{
    public void Configure(EntityTypeBuilder<ProductFamily> builder)
    {
        builder.ToTable("ProductFamilies");

        builder.HasKey(e => e.Id);

        // Bound taken from the entity, not restated here: the request validators enforce the same
        // number and cannot see this project.
        builder.Property(e => e.Name)
            .IsRequired()
            .HasMaxLength(ProductFamily.NameMaxLength);

        builder.Property(e => e.Description);

        // Not unique, on purpose. Two families may legitimately share a name, and a uniqueness
        // constraint would force the assisted flow to invent disambiguating suffixes when approving
        // hundreds of suggestions in one go — reintroducing the generated-key failure this entity
        // was created to remove. Indexed all the same, for the review screen's listing and search.
        builder.HasIndex(e => e.Name);

        // Stored as an int, never as a native PostgreSQL enum type: an enum type survives its table
        // being dropped, so a rollback leaves an orphan that makes a later migration fail with
        // "type already exists" — weeks later, and with no obvious connection to this change.
        builder.Property(e => e.Origin)
            .IsRequired()
            .HasConversion<int>();

        builder.Property(e => e.ApprovedByUserId);
        builder.Property(e => e.ApprovedAt);

        // Cursor for the indexing feed. It improves nothing measurable at ~350 families; it is here
        // because adding it later costs one of the six migration slots the plan allows, and having
        // it costs nothing. Renaming a family changes the denormalised family name of every one of
        // its members downstream, and no membership row is touched by that rename — so the feed
        // has to be able to find the change through the family itself.
        builder.HasIndex(e => e.UpdatedAt);

        // Members are owned by the family: they have no life of their own, so dissolving a family
        // takes them with it. This is the same split ComponentTemplate already uses — cascade from
        // the parent, restrict from the child towards what it references.
        builder.HasMany(e => e.Members)
            .WithOne(m => m.Family)
            .HasForeignKey(m => m.ProductFamilyId)
            .OnDelete(DeleteBehavior.Cascade);

        // Restrict, not the framework default. A required relationship defaults to Cascade, which
        // here would mean that deleting a user destroys the record of the approval they gave.
        builder.HasOne<User>()
            .WithMany()
            .HasForeignKey(e => e.ApprovedByUserId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
