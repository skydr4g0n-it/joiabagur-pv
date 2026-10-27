using System.Text.Json;
using Bogus;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;

namespace JoiabagurPV.Tests.TestHelpers;

/// <summary>
/// Test data generator using Bogus for creating fake entities.
/// </summary>
public static class TestDataGenerator
{
    private static readonly Faker _faker = new();

    /// <summary>
    /// Creates a User faker with customizable rules.
    /// </summary>
    public static Faker<User> UserFaker(UserRole? role = null, bool? isActive = null)
    {
        return new Faker<User>()
            .RuleFor(u => u.Id, f => f.Random.Guid())
            .RuleFor(u => u.Username, f => f.Internet.UserName())
            .RuleFor(u => u.PasswordHash, f => BCrypt.Net.BCrypt.HashPassword("TestPass123!", workFactor: 4))
            .RuleFor(u => u.FirstName, f => f.Name.FirstName())
            .RuleFor(u => u.LastName, f => f.Name.LastName())
            .RuleFor(u => u.Email, f => f.Internet.Email())
            .RuleFor(u => u.Role, f => role ?? f.PickRandom<UserRole>())
            .RuleFor(u => u.IsActive, f => isActive ?? true)
            .RuleFor(u => u.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(u => u.UpdatedAt, f => f.Date.Recent().ToUniversalTime())
            .RuleFor(u => u.LastLoginAt, f => f.Date.Recent().ToUniversalTime().OrNull(f));
    }

    /// <summary>
    /// Creates a single User with optional customization.
    /// </summary>
    public static User CreateUser(UserRole? role = null, bool? isActive = null, string? password = null)
    {
        var user = UserFaker(role, isActive).Generate();
        if (password != null)
        {
            user.PasswordHash = BCrypt.Net.BCrypt.HashPassword(password, workFactor: 4);
        }
        return user;
    }

    /// <summary>
    /// Creates multiple User instances.
    /// </summary>
    public static List<User> CreateUsers(int count, UserRole? role = null, bool? isActive = null)
    {
        return UserFaker(role, isActive).Generate(count);
    }

    /// <summary>
    /// Creates a RefreshToken faker with customizable rules.
    /// </summary>
    public static Faker<RefreshToken> RefreshTokenFaker(Guid? userId = null, bool? isRevoked = null, DateTime? expiresAt = null)
    {
        return new Faker<RefreshToken>()
            .RuleFor(r => r.Id, f => f.Random.Guid())
            .RuleFor(r => r.Token, f => Convert.ToBase64String(f.Random.Bytes(64)))
            .RuleFor(r => r.UserId, f => userId ?? f.Random.Guid())
            .RuleFor(r => r.ExpiresAt, f => expiresAt ?? DateTime.UtcNow.AddHours(8))
            .RuleFor(r => r.IsRevoked, f => isRevoked ?? false)
            .RuleFor(r => r.CreatedAt, f => f.Date.Recent().ToUniversalTime())
            .RuleFor(r => r.CreatedByIp, f => f.Internet.Ip());
    }

    /// <summary>
    /// Creates a single RefreshToken.
    /// </summary>
    public static RefreshToken CreateRefreshToken(Guid? userId = null, bool? isRevoked = null, DateTime? expiresAt = null, User? user = null)
    {
        var token = RefreshTokenFaker(userId, isRevoked, expiresAt).Generate();
        if (user != null)
        {
            token.UserId = user.Id;
            token.User = user;
        }
        return token;
    }

    /// <summary>
    /// Creates a UserPointOfSale faker.
    /// </summary>
    public static Faker<UserPointOfSale> UserPointOfSaleFaker(Guid? userId = null, Guid? pointOfSaleId = null, bool? isActive = null)
    {
        return new Faker<UserPointOfSale>()
            .RuleFor(u => u.Id, f => f.Random.Guid())
            .RuleFor(u => u.UserId, f => userId ?? f.Random.Guid())
            .RuleFor(u => u.PointOfSaleId, f => pointOfSaleId ?? f.Random.Guid())
            .RuleFor(u => u.IsActive, f => isActive ?? true)
            .RuleFor(u => u.AssignedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(u => u.CreatedAt, f => f.Date.Past().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single UserPointOfSale assignment.
    /// </summary>
    public static UserPointOfSale CreateUserPointOfSale(Guid? userId = null, Guid? pointOfSaleId = null, bool? isActive = null)
    {
        return UserPointOfSaleFaker(userId, pointOfSaleId, isActive).Generate();
    }

    /// <summary>
    /// Generates a random password that meets requirements.
    /// </summary>
    public static string GeneratePassword(int length = 12)
    {
        return _faker.Internet.Password(length, memorable: false, prefix: "Aa1!");
    }

    /// <summary>
    /// Creates a PointOfSale faker with customizable rules.
    /// </summary>
    public static Faker<PointOfSale> PointOfSaleFaker(bool? isActive = null)
    {
        return new Faker<PointOfSale>()
            .RuleFor(p => p.Id, f => f.Random.Guid())
            .RuleFor(p => p.Name, f => f.Company.CompanyName())
            .RuleFor(p => p.Code, f => f.Random.AlphaNumeric(6).ToUpperInvariant())
            .RuleFor(p => p.Address, f => f.Address.FullAddress())
            .RuleFor(p => p.Phone, f => f.Random.Replace("6#########"))
            .RuleFor(p => p.Email, f => f.Internet.Email())
            .RuleFor(p => p.IsActive, f => isActive ?? true)
            .RuleFor(p => p.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(p => p.UpdatedAt, f => f.Date.Recent().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single PointOfSale with optional customization.
    /// </summary>
    public static PointOfSale CreatePointOfSale(bool? isActive = null, string? code = null, string? name = null)
    {
        var pos = PointOfSaleFaker(isActive).Generate();
        if (code != null) pos.Code = code.ToUpperInvariant();
        if (name != null) pos.Name = name;
        return pos;
    }

    /// <summary>
    /// Creates multiple PointOfSale instances.
    /// </summary>
    public static List<PointOfSale> CreatePointOfSales(int count, bool? isActive = null)
    {
        return PointOfSaleFaker(isActive).Generate(count);
    }

    /// <summary>
    /// Creates a BaseEntity for testing (uses User as concrete implementation).
    /// This is for backwards compatibility with existing tests.
    /// </summary>
    public static BaseEntity CreateBaseEntity()
    {
        return CreateUser();
    }

    /// <summary>
    /// Creates multiple BaseEntity instances for testing.
    /// </summary>
    public static IEnumerable<BaseEntity> CreateBaseEntities(int count)
    {
        return CreateUsers(count).Cast<BaseEntity>();
    }

    /// <summary>
    /// Creates a Product faker with customizable rules.
    /// </summary>
    public static Faker<Product> ProductFaker(bool? isActive = null, Guid? collectionId = null)
    {
        return new Faker<Product>()
            .RuleFor(p => p.Id, f => f.Random.Guid())
            .RuleFor(p => p.SKU, f => $"JOY-{f.Random.Number(1000, 9999)}")
            .RuleFor(p => p.Name, f => f.Commerce.ProductName())
            .RuleFor(p => p.Description, f => f.Commerce.ProductDescription())
            .RuleFor(p => p.Price, f => f.Random.Decimal(10, 5000))
            .RuleFor(p => p.CollectionId, f => collectionId)
            .RuleFor(p => p.IsActive, f => isActive ?? true)
            .RuleFor(p => p.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(p => p.UpdatedAt, f => f.Date.Recent().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single Product with optional customization.
    /// </summary>
    public static Product CreateProduct(bool? isActive = null, string? sku = null, string? name = null, decimal? price = null, Guid? collectionId = null)
    {
        var product = ProductFaker(isActive, collectionId).Generate();
        if (sku != null) product.SKU = sku;
        if (name != null) product.Name = name;
        if (price.HasValue) product.Price = price.Value;
        return product;
    }

    /// <summary>
    /// Creates multiple Product instances.
    /// </summary>
    public static List<Product> CreateProducts(int count, bool? isActive = null, Guid? collectionId = null)
    {
        return ProductFaker(isActive, collectionId).Generate(count);
    }

    /// <summary>
    /// Creates a Collection faker with customizable rules.
    /// </summary>
    public static Faker<Collection> CollectionFaker()
    {
        return new Faker<Collection>()
            .RuleFor(c => c.Id, f => f.Random.Guid())
            .RuleFor(c => c.Name, f => f.Commerce.Department())
            .RuleFor(c => c.Description, f => f.Lorem.Sentence())
            .RuleFor(c => c.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(c => c.UpdatedAt, f => f.Date.Recent().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single Collection with optional customization.
    /// </summary>
    public static Collection CreateCollection(string? name = null, string? description = null)
    {
        var collection = CollectionFaker().Generate();
        if (name != null) collection.Name = name;
        if (description != null) collection.Description = description;
        return collection;
    }

    /// <summary>
    /// Creates multiple Collection instances.
    /// </summary>
    public static List<Collection> CreateCollections(int count)
    {
        return CollectionFaker().Generate(count);
    }

    /// <summary>
    /// Creates a ProductPhoto faker with customizable rules.
    /// </summary>
    public static Faker<ProductPhoto> ProductPhotoFaker(Guid? productId = null, bool? isPrimary = null)
    {
        return new Faker<ProductPhoto>()
            .RuleFor(pp => pp.Id, f => f.Random.Guid())
            .RuleFor(pp => pp.ProductId, f => productId ?? f.Random.Guid())
            .RuleFor(pp => pp.FileName, f => $"{f.Random.AlphaNumeric(8)}.jpg")
            .RuleFor(pp => pp.DisplayOrder, f => f.Random.Int(0, 10))
            .RuleFor(pp => pp.IsPrimary, f => isPrimary ?? false)
            .RuleFor(pp => pp.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(pp => pp.UpdatedAt, f => f.Date.Recent().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single ProductPhoto with optional customization.
    /// </summary>
    public static ProductPhoto CreateProductPhoto(Guid? productId = null, bool? isPrimary = null, string? fileName = null)
    {
        var photo = ProductPhotoFaker(productId, isPrimary).Generate();
        if (fileName != null) photo.FileName = fileName;
        return photo;
    }

    /// <summary>
    /// Creates an Inventory faker with customizable rules.
    /// </summary>
    public static Faker<Inventory> InventoryFaker(Guid? productId = null, Guid? pointOfSaleId = null, bool? isActive = null, int? quantity = null)
    {
        return new Faker<Inventory>()
            .RuleFor(i => i.Id, f => f.Random.Guid())
            .RuleFor(i => i.ProductId, f => productId ?? f.Random.Guid())
            .RuleFor(i => i.PointOfSaleId, f => pointOfSaleId ?? f.Random.Guid())
            .RuleFor(i => i.Quantity, f => quantity ?? f.Random.Int(0, 100))
            .RuleFor(i => i.IsActive, f => isActive ?? true)
            .RuleFor(i => i.LastUpdatedAt, f => f.Date.Recent().ToUniversalTime())
            .RuleFor(i => i.CreatedAt, f => f.Date.Past().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single Inventory with optional customization.
    /// </summary>
    public static Inventory CreateInventory(Guid? productId = null, Guid? pointOfSaleId = null, bool? isActive = null, int? quantity = null)
    {
        return InventoryFaker(productId, pointOfSaleId, isActive, quantity).Generate();
    }

    /// <summary>
    /// Creates multiple Inventory instances.
    /// </summary>
    public static List<Inventory> CreateInventories(int count, Guid? productId = null, Guid? pointOfSaleId = null, bool? isActive = null)
    {
        return InventoryFaker(productId, pointOfSaleId, isActive).Generate(count);
    }

    /// <summary>
    /// Creates an InventoryMovement faker with customizable rules.
    /// </summary>
    public static Faker<InventoryMovement> InventoryMovementFaker(Guid? inventoryId = null, Guid? userId = null, MovementType? movementType = null)
    {
        return new Faker<InventoryMovement>()
            .RuleFor(m => m.Id, f => f.Random.Guid())
            .RuleFor(m => m.InventoryId, f => inventoryId ?? f.Random.Guid())
            .RuleFor(m => m.UserId, f => userId ?? f.Random.Guid())
            .RuleFor(m => m.MovementType, f => movementType ?? f.PickRandom<MovementType>())
            .RuleFor(m => m.QuantityChange, f => f.Random.Int(-50, 50))
            .RuleFor(m => m.QuantityBefore, f => f.Random.Int(0, 100))
            .RuleFor(m => m.QuantityAfter, (f, m) => m.QuantityBefore + m.QuantityChange)
            .RuleFor(m => m.Reason, f => f.Lorem.Sentence())
            .RuleFor(m => m.MovementDate, f => f.Date.Recent().ToUniversalTime())
            .RuleFor(m => m.CreatedAt, f => f.Date.Past().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single InventoryMovement with optional customization.
    /// </summary>
    public static InventoryMovement CreateInventoryMovement(Guid? inventoryId = null, Guid? userId = null, MovementType? movementType = null)
    {
        return InventoryMovementFaker(inventoryId, userId, movementType).Generate();
    }

    /// <summary>
    /// Creates multiple InventoryMovement instances.
    /// </summary>
    public static List<InventoryMovement> CreateInventoryMovements(int count, Guid? inventoryId = null, Guid? userId = null)
    {
        return InventoryMovementFaker(inventoryId, userId).Generate(count);
    }

    /// <summary>
    /// Creates a Sale faker with customizable rules.
    /// </summary>
    public static Faker<Sale> SaleFaker(Guid? productId = null, Guid? pointOfSaleId = null, Guid? paymentMethodId = null, Guid? userId = null, int? quantity = null, decimal? price = null)
    {
        return new Faker<Sale>()
            .RuleFor(s => s.Id, f => f.Random.Guid())
            .RuleFor(s => s.ProductId, f => productId ?? f.Random.Guid())
            .RuleFor(s => s.PointOfSaleId, f => pointOfSaleId ?? f.Random.Guid())
            .RuleFor(s => s.PaymentMethodId, f => paymentMethodId ?? f.Random.Guid())
            .RuleFor(s => s.UserId, f => userId ?? f.Random.Guid())
            .RuleFor(s => s.Quantity, f => quantity ?? f.Random.Int(1, 5))
            .RuleFor(s => s.Price, f => price ?? f.Random.Decimal(10, 1000))
            .RuleFor(s => s.SaleDate, f => f.Date.Recent(10).ToUniversalTime())
            .RuleFor(s => s.Notes, f => f.Lorem.Sentence().OrNull(f))
            .RuleFor(s => s.CreatedAt, f => f.Date.Past().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single Sale with optional customization.
    /// </summary>
    public static Sale CreateSale(Guid? productId = null, Guid? pointOfSaleId = null, Guid? paymentMethodId = null, Guid? userId = null, int? quantity = null, decimal? price = null, DateTime? saleDate = null)
    {
        var sale = SaleFaker(productId, pointOfSaleId, paymentMethodId, userId, quantity, price).Generate();
        if (saleDate.HasValue) sale.SaleDate = saleDate.Value;
        return sale;
    }

    /// <summary>
    /// Creates multiple Sale instances.
    /// </summary>
    public static List<Sale> CreateSales(int count, Guid? productId = null, Guid? pointOfSaleId = null)
    {
        return SaleFaker(productId, pointOfSaleId).Generate(count);
    }

    /// <summary>
    /// Creates a PaymentMethod faker with customizable rules.
    /// </summary>
    public static Faker<PaymentMethod> PaymentMethodFaker(bool? isActive = null)
    {
        return new Faker<PaymentMethod>()
            .RuleFor(pm => pm.Id, f => f.Random.Guid())
            .RuleFor(pm => pm.Code, f => f.Random.AlphaNumeric(6).ToUpperInvariant())
            .RuleFor(pm => pm.Name, f => f.Finance.AccountName())
            .RuleFor(pm => pm.Description, f => f.Lorem.Sentence())
            .RuleFor(pm => pm.IsActive, f => isActive ?? true)
            .RuleFor(pm => pm.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(pm => pm.UpdatedAt, f => f.Date.Recent().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single PaymentMethod with optional customization.
    /// </summary>
    public static PaymentMethod CreatePaymentMethod(bool? isActive = null, string? code = null, string? name = null)
    {
        var pm = PaymentMethodFaker(isActive).Generate();
        if (code != null) pm.Code = code;
        if (name != null) pm.Name = name;
        return pm;
    }

    /// <summary>
    /// Creates a Return faker with customizable rules.
    /// </summary>
    public static Faker<Return> ReturnFaker(Guid? productId = null, Guid? pointOfSaleId = null, Guid? userId = null, int? quantity = null, ReturnCategory? category = null)
    {
        return new Faker<Return>()
            .RuleFor(r => r.Id, f => f.Random.Guid())
            .RuleFor(r => r.ProductId, f => productId ?? f.Random.Guid())
            .RuleFor(r => r.PointOfSaleId, f => pointOfSaleId ?? f.Random.Guid())
            .RuleFor(r => r.UserId, f => userId ?? f.Random.Guid())
            .RuleFor(r => r.Quantity, f => quantity ?? f.Random.Int(1, 5))
            .RuleFor(r => r.Category, f => category ?? f.PickRandom<ReturnCategory>())
            .RuleFor(r => r.Reason, f => f.Lorem.Sentence().OrNull(f))
            .RuleFor(r => r.ReturnDate, f => f.Date.Recent().ToUniversalTime())
            .RuleFor(r => r.CreatedAt, f => f.Date.Past().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single Return with optional customization.
    /// </summary>
    public static Return CreateReturn(Guid? productId = null, Guid? pointOfSaleId = null, Guid? userId = null, int? quantity = null, ReturnCategory? category = null)
    {
        return ReturnFaker(productId, pointOfSaleId, userId, quantity, category).Generate();
    }

    /// <summary>
    /// Creates a ReturnSale faker with customizable rules.
    /// </summary>
    public static Faker<ReturnSale> ReturnSaleFaker(Guid? returnId = null, Guid? saleId = null, int? quantity = null, decimal? unitPrice = null)
    {
        return new Faker<ReturnSale>()
            .RuleFor(rs => rs.Id, f => f.Random.Guid())
            .RuleFor(rs => rs.ReturnId, f => returnId ?? f.Random.Guid())
            .RuleFor(rs => rs.SaleId, f => saleId ?? f.Random.Guid())
            .RuleFor(rs => rs.Quantity, f => quantity ?? f.Random.Int(1, 5))
            .RuleFor(rs => rs.UnitPrice, f => unitPrice ?? f.Random.Decimal(10, 1000))
            .RuleFor(rs => rs.CreatedAt, f => f.Date.Past().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single ReturnSale with optional customization.
    /// </summary>
    public static ReturnSale CreateReturnSale(Guid? returnId = null, Guid? saleId = null, int? quantity = null, decimal? unitPrice = null)
    {
        return ReturnSaleFaker(returnId, saleId, quantity, unitPrice).Generate();
    }

    /// <summary>
    /// Generates a realistic 1280-dimensional float vector (random unit-normalised values).
    /// </summary>
    public static float[] CreateEmbeddingVector(int dimension = 1280)
    {
        var random = new Random();
        var vector = new float[dimension];
        double norm = 0;
        for (int i = 0; i < dimension; i++)
        {
            vector[i] = (float)(random.NextDouble() * 2 - 1);
            norm += vector[i] * vector[i];
        }
        norm = Math.Sqrt(norm);
        for (int i = 0; i < dimension; i++)
        {
            vector[i] = (float)(vector[i] / norm);
        }
        return vector;
    }

    /// <summary>
    /// Creates a ProductPhotoEmbedding faker with customizable rules.
    /// </summary>
    public static Faker<ProductPhotoEmbedding> ProductPhotoEmbeddingFaker(
        Guid? productPhotoId = null,
        Guid? productId = null,
        string? sku = null,
        float[]? vector = null)
    {
        return new Faker<ProductPhotoEmbedding>()
            .RuleFor(e => e.Id, f => f.Random.Guid())
            .RuleFor(e => e.ProductPhotoId, f => productPhotoId ?? f.Random.Guid())
            .RuleFor(e => e.ProductId, f => productId ?? f.Random.Guid())
            .RuleFor(e => e.ProductSku, f => sku ?? f.Commerce.Ean8())
            .RuleFor(e => e.EmbeddingVector, _ => JsonSerializer.Serialize(vector ?? CreateEmbeddingVector()))
            .RuleFor(e => e.CreatedAt, f => f.Date.Past().ToUniversalTime())
            .RuleFor(e => e.UpdatedAt, f => f.Date.Recent().ToUniversalTime());
    }

    /// <summary>
    /// Creates a single ProductPhotoEmbedding with optional customization.
    /// </summary>
    public static ProductPhotoEmbedding CreateProductPhotoEmbedding(
        Guid? productPhotoId = null,
        Guid? productId = null,
        string? sku = null,
        float[]? vector = null)
    {
        return ProductPhotoEmbeddingFaker(productPhotoId, productId, sku, vector).Generate();
    }

    /// <summary>
    /// Creates multiple ProductPhotoEmbedding instances.
    /// </summary>
    public static List<ProductPhotoEmbedding> CreateProductPhotoEmbeddings(
        int count,
        Guid? productPhotoId = null,
        Guid? productId = null,
        string? sku = null)
    {
        return ProductPhotoEmbeddingFaker(productPhotoId, productId, sku).Generate(count);
    }
}