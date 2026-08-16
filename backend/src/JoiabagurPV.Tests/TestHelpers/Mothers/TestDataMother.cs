using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Infrastructure.Data;
using Microsoft.Extensions.DependencyInjection;

namespace JoiabagurPV.Tests.TestHelpers.Mothers;

/// <summary>
/// Factory class for creating Mother Objects in integration tests.
/// Provides a fluent interface for building complex test scenarios.
/// 
/// Mother Objects use Bogus (via TestDataGenerator) for realistic default values
/// and handle database persistence. Use TestDataGenerator directly for unit tests
/// with mocked repositories.
/// </summary>
public class TestDataMother : IDisposable
{
    private readonly IServiceScope _scope;
    private readonly ApplicationDbContext _context;

    public TestDataMother(IServiceProvider serviceProvider)
    {
        _scope = serviceProvider.CreateScope();
        _context = _scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    }

    /// <summary>
    /// The database context for direct access when needed.
    /// </summary>
    public ApplicationDbContext Context => _context;

    /// <summary>
    /// Creates a new SaleMother for building Sale entities.
    /// </summary>
    public SaleMother Sale() => new(_context);

    /// <summary>
    /// Creates a new ReturnMother for building Return entities.
    /// </summary>
    public ReturnMother Return() => new(_context);

    /// <summary>
    /// Creates a new ProductMother for building Product entities.
    /// </summary>
    public ProductMother Product() => new(_context);

    /// <summary>
    /// Creates a new PointOfSaleMother for building PointOfSale entities.
    /// </summary>
    public PointOfSaleMother PointOfSale() => new(_context);

    /// <summary>
    /// Creates a new PaymentMethodMother for building PaymentMethod entities.
    /// </summary>
    public PaymentMethodMother PaymentMethod() => new(_context);

    /// <summary>
    /// Creates a new InventoryMother for building Inventory and related entities.
    /// </summary>
    public InventoryMother Inventory() => new(_context);

    /// <summary>
    /// Creates a new UserMother for building User entities.
    /// </summary>
    public UserMother User() => new(_context);

    /// <summary>
    /// Creates a new ProductPhotoEmbeddingMother for building ProductPhotoEmbedding entities.
    /// </summary>
    public ProductPhotoEmbeddingMother ProductPhotoEmbedding() => new(_context);

    /// <summary>
    /// Creates a new ProductFamilyMother for building ProductFamily entities with their members.
    /// </summary>
    public ProductFamilyMother ProductFamily() => new(_context);

    public void Dispose()
    {
        _scope.Dispose();
    }
}

/// <summary>
/// Mother Object for creating ProductFamily entities together with their members.
/// </summary>
/// <remarks>
/// Members are added through <see cref="WithMember"/> so their position comes from the order they
/// were declared, exactly as the service derives it. A test that wants to assert ordering must not
/// be the place where the ordering is invented.
/// </remarks>
public class ProductFamilyMother
{
    private readonly ApplicationDbContext _context;
    private readonly ProductFamily _family;
    private readonly List<ProductFamilyMember> _members = [];

    public ProductFamilyMother(ApplicationDbContext context)
    {
        _context = context;
        _family = new ProductFamily { Name = "Familia de prueba" };
    }

    public ProductFamilyMother WithName(string name) { _family.Name = name; return this; }

    public ProductFamilyMother WithDescription(string description)
    {
        _family.Description = description;
        return this;
    }

    /// <summary>
    /// Adds a member at the next free position, with an optional variant label.
    /// </summary>
    public ProductFamilyMother WithMember(Guid productId, string? variantLabel = null)
    {
        _members.Add(new ProductFamilyMember
        {
            ProductId = productId,
            VariantLabel = variantLabel,
            SortOrder = _members.Count
        });

        return this;
    }

    public async Task<ProductFamily> CreateAsync()
    {
        foreach (var member in _members)
        {
            _family.Members.Add(member);
        }

        _context.ProductFamilies.Add(_family);
        await _context.SaveChangesAsync();
        return _family;
    }
}

/// <summary>
/// Mother Object for creating Product entities.
/// Uses Bogus via TestDataGenerator for realistic default values.
/// </summary>
public class ProductMother
{
    private readonly ApplicationDbContext _context;
    private readonly Product _product;

    public ProductMother(ApplicationDbContext context)
    {
        _context = context;
        // Start with a Bogus-generated entity with realistic values
        _product = TestDataGenerator.CreateProduct();
    }

    public ProductMother WithSku(string sku) { _product.SKU = sku; return this; }
    public ProductMother WithName(string name) { _product.Name = name; return this; }
    public ProductMother WithDescription(string description) { _product.Description = description; return this; }
    public ProductMother WithPrice(decimal price) { _product.Price = price; return this; }
    public ProductMother Inactive() { _product.IsActive = false; return this; }
    public ProductMother WithCollection(Guid collectionId) { _product.CollectionId = collectionId; return this; }

    public async Task<Product> CreateAsync()
    {
        _context.Products.Add(_product);
        await _context.SaveChangesAsync();
        return _product;
    }
}

/// <summary>
/// Mother Object for creating PointOfSale entities.
/// Uses Bogus via TestDataGenerator for realistic default values.
/// </summary>
public class PointOfSaleMother
{
    private readonly ApplicationDbContext _context;
    private readonly PointOfSale _pos;

    public PointOfSaleMother(ApplicationDbContext context)
    {
        _context = context;
        _pos = TestDataGenerator.CreatePointOfSale();
    }

    public PointOfSaleMother WithCode(string code) { _pos.Code = code.ToUpperInvariant(); return this; }
    public PointOfSaleMother WithName(string name) { _pos.Name = name; return this; }
    public PointOfSaleMother WithAddress(string address) { _pos.Address = address; return this; }
    public PointOfSaleMother WithPhone(string phone) { _pos.Phone = phone; return this; }
    public PointOfSaleMother WithEmail(string email) { _pos.Email = email; return this; }
    public PointOfSaleMother Inactive() { _pos.IsActive = false; return this; }
    public PointOfSaleMother WithAllowManualPriceEdit(bool allow = true) { _pos.AllowManualPriceEdit = allow; return this; }

    public async Task<PointOfSale> CreateAsync()
    {
        _context.PointOfSales.Add(_pos);
        await _context.SaveChangesAsync();
        return _pos;
    }
}

/// <summary>
/// Mother Object for creating PaymentMethod entities.
/// Uses Bogus via TestDataGenerator for realistic default values.
/// </summary>
public class PaymentMethodMother
{
    private readonly ApplicationDbContext _context;
    private readonly PaymentMethod _pm;

    public PaymentMethodMother(ApplicationDbContext context)
    {
        _context = context;
        _pm = TestDataGenerator.CreatePaymentMethod();
    }

    public PaymentMethodMother WithCode(string code) { _pm.Code = code.ToUpperInvariant(); return this; }
    public PaymentMethodMother WithName(string name) { _pm.Name = name; return this; }
    public PaymentMethodMother WithDescription(string description) { _pm.Description = description; return this; }
    public PaymentMethodMother Inactive() { _pm.IsActive = false; return this; }

    public async Task<PaymentMethod> CreateAsync()
    {
        _context.PaymentMethods.Add(_pm);
        await _context.SaveChangesAsync();
        return _pm;
    }
}

/// <summary>
/// Mother Object for creating Inventory entities.
/// Uses Bogus via TestDataGenerator for realistic default values.
/// </summary>
public class InventoryMother
{
    private readonly ApplicationDbContext _context;
    private readonly Inventory _inventory;

    public InventoryMother(ApplicationDbContext context)
    {
        _context = context;
        _inventory = TestDataGenerator.CreateInventory();
    }

    public InventoryMother WithProduct(Guid productId) { _inventory.ProductId = productId; return this; }
    public InventoryMother WithPointOfSale(Guid pointOfSaleId) { _inventory.PointOfSaleId = pointOfSaleId; return this; }
    public InventoryMother WithQuantity(int quantity) { _inventory.Quantity = quantity; return this; }
    public InventoryMother Inactive() { _inventory.IsActive = false; return this; }

    public async Task<Inventory> CreateAsync()
    {
        if (_inventory.ProductId == Guid.Empty)
            throw new InvalidOperationException("ProductId is required. Call WithProduct().");
        if (_inventory.PointOfSaleId == Guid.Empty)
            throw new InvalidOperationException("PointOfSaleId is required. Call WithPointOfSale().");

        _context.Inventories.Add(_inventory);
        await _context.SaveChangesAsync();
        return _inventory;
    }
}

/// <summary>
/// Mother Object for creating User entities.
/// Uses Bogus via TestDataGenerator for realistic default values.
/// </summary>
public class UserMother
{
    private readonly ApplicationDbContext _context;
    private readonly User _user;
    private readonly List<Guid> _assignedPointOfSales = new();

    public UserMother(ApplicationDbContext context)
    {
        _context = context;
        // Create user with Operator role by default (most common in tests)
        _user = TestDataGenerator.CreateUser(role: UserRole.Operator, password: "Test123!");
    }

    public UserMother WithUsername(string username) { _user.Username = username; return this; }
    public UserMother WithName(string firstName, string lastName) 
    { 
        _user.FirstName = firstName; 
        _user.LastName = lastName; 
        return this; 
    }
    public UserMother WithEmail(string email) { _user.Email = email; return this; }
    public UserMother WithRole(UserRole role) { _user.Role = role; return this; }
    public UserMother AsAdmin() { _user.Role = UserRole.Administrator; return this; }
    public UserMother AsOperator() { _user.Role = UserRole.Operator; return this; }
    public UserMother Inactive() { _user.IsActive = false; return this; }
    public UserMother AssignedTo(Guid pointOfSaleId) { _assignedPointOfSales.Add(pointOfSaleId); return this; }

    public async Task<User> CreateAsync()
    {
        _context.Users.Add(_user);

        // Add POS assignments
        foreach (var posId in _assignedPointOfSales)
        {
            _context.UserPointOfSales.Add(new UserPointOfSale
            {
                Id = Guid.NewGuid(),
                UserId = _user.Id,
                PointOfSaleId = posId,
                IsActive = true,
                AssignedAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow
            });
        }

        await _context.SaveChangesAsync();
        return _user;
    }
}
