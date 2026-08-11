using JoiabagurPV.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace JoiabagurPV.Infrastructure.Data;

/// <summary>
/// Application database context for Entity Framework Core.
/// </summary>
public class ApplicationDbContext : DbContext
{
    /// <summary>
    /// Initializes a new instance of the ApplicationDbContext class.
    /// </summary>
    /// <param name="options">The options to be used by a DbContext.</param>
    public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
        : base(options)
    {
    }

    /// <summary>
    /// Gets or sets the Users DbSet.
    /// </summary>
    public DbSet<User> Users { get; set; }

    /// <summary>
    /// Gets or sets the UserPointOfSales DbSet.
    /// </summary>
    public DbSet<UserPointOfSale> UserPointOfSales { get; set; }

    /// <summary>
    /// Gets or sets the RefreshTokens DbSet.
    /// </summary>
    public DbSet<RefreshToken> RefreshTokens { get; set; }

    /// <summary>
    /// Gets or sets the PointOfSales DbSet.
    /// </summary>
    public DbSet<PointOfSale> PointOfSales { get; set; }

    /// <summary>
    /// Gets or sets the PaymentMethods DbSet.
    /// </summary>
    public DbSet<PaymentMethod> PaymentMethods { get; set; }

    /// <summary>
    /// Gets or sets the PointOfSalePaymentMethods DbSet.
    /// </summary>
    public DbSet<PointOfSalePaymentMethod> PointOfSalePaymentMethods { get; set; }

    /// <summary>
    /// Gets or sets the Products DbSet.
    /// </summary>
    public DbSet<Product> Products { get; set; }

    /// <summary>
    /// Gets or sets the ProductPhotos DbSet.
    /// </summary>
    public DbSet<ProductPhoto> ProductPhotos { get; set; }

    /// <summary>
    /// Gets or sets the Collections DbSet.
    /// </summary>
    public DbSet<Collection> Collections { get; set; }

    /// <summary>
    /// Gets or sets the Inventories DbSet.
    /// </summary>
    public DbSet<Inventory> Inventories { get; set; }

    /// <summary>
    /// Gets or sets the InventoryMovements DbSet.
    /// </summary>
    public DbSet<InventoryMovement> InventoryMovements { get; set; }

    /// <summary>
    /// Gets or sets the Sales DbSet.
    /// </summary>
    public DbSet<Sale> Sales { get; set; }

    /// <summary>
    /// Gets or sets the SalePhotos DbSet.
    /// </summary>
    public DbSet<SalePhoto> SalePhotos { get; set; }

    /// <summary>
    /// Gets or sets the Returns DbSet.
    /// </summary>
    public DbSet<Return> Returns { get; set; }

    /// <summary>
    /// Gets or sets the ReturnSales DbSet (junction table for Return-Sale many-to-many).
    /// </summary>
    public DbSet<ReturnSale> ReturnSales { get; set; }

    /// <summary>
    /// Gets or sets the ReturnPhotos DbSet.
    /// </summary>
    public DbSet<ReturnPhoto> ReturnPhotos { get; set; }

    /// <summary>
    /// Gets or sets the ModelMetadata DbSet.
    /// </summary>
    public DbSet<ModelMetadata> ModelMetadata { get; set; }

    /// <summary>
    /// Gets or sets the ModelTrainingJobs DbSet.
    /// </summary>
    public DbSet<ModelTrainingJob> ModelTrainingJobs { get; set; }

    /// <summary>
    /// Gets or sets the ProductComponents DbSet (master table).
    /// </summary>
    public DbSet<ProductComponent> ProductComponents { get; set; }

    /// <summary>
    /// Gets or sets the ProductComponentAssignments DbSet.
    /// </summary>
    public DbSet<ProductComponentAssignment> ProductComponentAssignments { get; set; }

    /// <summary>
    /// Gets or sets the ComponentTemplates DbSet.
    /// </summary>
    public DbSet<ComponentTemplate> ComponentTemplates { get; set; }

    /// <summary>
    /// Gets or sets the ComponentTemplateItems DbSet.
    /// </summary>
    public DbSet<ComponentTemplateItem> ComponentTemplateItems { get; set; }

    /// <summary>
    /// Gets or sets the ProductPhotoEmbeddings DbSet.
    /// </summary>
    public DbSet<ProductPhotoEmbedding> ProductPhotoEmbeddings { get; set; }

    /// <summary>
    /// Gets or sets the ProductSearchEvents DbSet.
    /// </summary>
    public DbSet<ProductSearchEvent> ProductSearchEvents { get; set; }

    /// <summary>
    /// Configures the model that was discovered by convention from the entity types
    /// exposed in Microsoft.EntityFrameworkCore.DbSet`1 properties on your derived context.
    /// </summary>
    /// <param name="modelBuilder">The builder being used to construct the model for this context.</param>
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // Apply configurations from the assembly
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ApplicationDbContext).Assembly);

        // Configure base entity properties
        foreach (var entityType in modelBuilder.Model.GetEntityTypes())
        {
            if (typeof(BaseEntity).IsAssignableFrom(entityType.ClrType))
            {
                modelBuilder.Entity(entityType.ClrType)
                    .Property<DateTime>("CreatedAt")
                    .HasDefaultValueSql("NOW()")
                    .ValueGeneratedOnAdd();

                modelBuilder.Entity(entityType.ClrType)
                    .Property<DateTime>("UpdatedAt")
                    .HasDefaultValueSql("NOW()")
                    .ValueGeneratedOnAddOrUpdate();
            }
        }
    }

    /// <summary>
    /// Saves all changes made in this context to the database.
    /// </summary>
    /// <param name="cancellationToken">A CancellationToken to observe while waiting for the task to complete.</param>
    /// <returns>A task that represents the asynchronous save operation.</returns>
    public override Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
    {
        // Automatically update UpdatedAt timestamp
        foreach (var entry in ChangeTracker.Entries<BaseEntity>())
        {
            if (entry.State == EntityState.Modified)
            {
                entry.Entity.UpdatedAt = DateTime.UtcNow;
            }
        }

        return base.SaveChangesAsync(cancellationToken);
    }
}