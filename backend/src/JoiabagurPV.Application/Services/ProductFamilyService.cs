using System.Data.Common;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Enums;
using JoiabagurPV.Domain.Interfaces.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Manages product families and the declaration of their membership.
/// </summary>
public class ProductFamilyService : IProductFamilyService
{
    private readonly IProductFamilyRepository _familyRepository;
    private readonly IProductRepository _productRepository;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ProductFamilyService> _logger;

    public ProductFamilyService(
        IProductFamilyRepository familyRepository,
        IProductRepository productRepository,
        IUnitOfWork unitOfWork,
        ILogger<ProductFamilyService> logger)
    {
        _familyRepository = familyRepository;
        _productRepository = productRepository;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    /// <inheritdoc/>
    public async Task<ProductFamilyDto> CreateAsync(CreateProductFamilyRequest request)
    {
        var declared = Normalise(request.Members);
        await GuardAgainstOtherFamiliesAsync(declared, Guid.Empty);

        var family = new ProductFamily
        {
            Name = request.Name.Trim(),
            Description = request.Description?.Trim(),
            // Only ever Manual here. The assisted flow writes the other value, along with who
            // approved and when — which is why those three columns exist from the first migration.
            Origin = FamilyOrigin.Manual,
            Members = BuildMembers(declared)
        };

        await _familyRepository.AddAsync(family);
        await SaveTranslatingMembershipRaceAsync(declared);

        _logger.LogInformation(
            "product_family_created {FamilyId} {MemberCount}", family.Id, family.Members.Count);

        return await ReadBackAsync(family.Id);
    }

    /// <inheritdoc/>
    public async Task<ProductFamilyDto?> GetByIdAsync(Guid id)
    {
        var family = await _familyRepository.GetWithMembersAsync(id);
        return family is null ? null : await MapAsync(family);
    }

    /// <inheritdoc/>
    public async Task<ProductFamilyDto> UpdateAsync(Guid id, UpdateProductFamilyRequest request)
    {
        var family = await _familyRepository.GetWithMembersAsync(id)
            ?? throw new KeyNotFoundException($"Familia con ID {id} no encontrada.");

        family.Name = request.Name.Trim();
        family.Description = request.Description?.Trim();

        // Tracked entity: the change tracker already holds the two edited properties, and marking
        // the root Modified would only widen the update to columns nobody touched.
        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("product_family_renamed {FamilyId}", family.Id);

        return await ReadBackAsync(family.Id);
    }

    /// <inheritdoc/>
    public async Task<ProductFamilyDto> ReplaceMembersAsync(Guid id, ReplaceFamilyMembersRequest request)
    {
        var family = await _familyRepository.GetWithMembersAsync(id)
            ?? throw new KeyNotFoundException($"Familia con ID {id} no encontrada.");

        var declared = Normalise(request.Members);

        if (AlreadyMatches(family, declared))
        {
            // Nothing to write. Rewriting identical rows would bump their timestamps and hand the
            // indexing feed a change that did not happen, making it re-emit every member of the
            // family for no reason.
            _logger.LogInformation("product_family_members_unchanged {FamilyId}", family.Id);
            return await MapAsync(family);
        }

        await GuardAgainstOtherFamiliesAsync(declared, family.Id);

        // Replaced wholesale rather than reconciled row by row. Matching on product and updating in
        // place would preserve each row's identity — which nothing references — at the cost of
        // turning a reorder into a cycle: swapping two positions means each row moving to a value
        // the other still holds, and an UPDATE cannot be split into a delete plus an insert the way
        // this can. Deleting everything and inserting the new set leaves the change tracker an
        // acyclic graph it orders on its own.
        await ReplaceMembersInPlaceAsync(family, declared);

        _logger.LogInformation(
            "product_family_members_replaced {FamilyId} {MemberCount}", family.Id, declared.Count);

        return await ReadBackAsync(family.Id);
    }

    /// <inheritdoc/>
    public async Task<ProductFamilyDto?> GetByProductIdAsync(Guid productId)
    {
        if (!await _productRepository.ExistsAsync(productId))
        {
            throw new KeyNotFoundException($"Producto con ID {productId} no encontrado.");
        }

        var family = await _familyRepository.GetByProductIdAsync(productId);
        return family is null ? null : await MapAsync(family);
    }

    /// <summary>
    /// Removes every current member and inserts the declared set, in one flush.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Both halves are stated to the change tracker <strong>explicitly</strong> rather than by
    /// mutating the family's collection. That is the part that matters:
    /// <see cref="Domain.Entities.BaseEntity"/> assigns the identifier in its constructor, so a
    /// member reached through a navigation property arrives with a non-empty key and is taken for a
    /// row that already exists — the write then goes out as an update against nothing and fails with
    /// a concurrency error naming neither the entity nor the cause. Reordering and label swaps are
    /// where it shows, because those are the declarations that delete and insert at once.
    /// </para>
    /// <para>
    /// One flush is enough, and that was measured rather than assumed: the change tracker adds
    /// dependency edges between commands that touch the same unique index value, so the deletes are
    /// ordered ahead of the inserts that reuse a position or a label. Staging the write in two saves
    /// was tried and removed — it passed too, and bought nothing.
    /// </para>
    /// </remarks>
    private async Task ReplaceMembersInPlaceAsync(
        ProductFamily family,
        List<ProductFamilyMemberRequest> declared)
    {
        await _familyRepository.RemoveMembersAsync(family.Members.ToList());

        var fresh = BuildMembers(declared);
        foreach (var member in fresh)
        {
            member.ProductFamilyId = family.Id;
        }

        await _familyRepository.AddMembersAsync(fresh);
        await SaveTranslatingMembershipRaceAsync(declared);
    }

    // ── Membership rules ──────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Trims the declared labels and drops blank ones to null.
    /// </summary>
    /// <remarks>
    /// An empty string and an absent label mean the same thing — the variant is not known yet — but
    /// they behave differently against a unique index: PostgreSQL treats nulls as distinct and empty
    /// strings as equal, so two unlabelled members sent as <c>""</c> would collide while the same
    /// two sent as null would not. Normalising here is what makes that difference invisible to
    /// callers instead of a puzzle.
    /// </remarks>
    private static List<ProductFamilyMemberRequest> Normalise(List<ProductFamilyMemberRequest> members) =>
        members
            .Select(member => new ProductFamilyMemberRequest
            {
                ProductId = member.ProductId,
                VariantLabel = string.IsNullOrWhiteSpace(member.VariantLabel)
                    ? null
                    : member.VariantLabel.Trim()
            })
            .ToList();

    /// <summary>
    /// Turns the declared list into members, taking each position from its place in the list.
    /// </summary>
    private static List<ProductFamilyMember> BuildMembers(List<ProductFamilyMemberRequest> declared) =>
        declared
            .Select((member, index) => new ProductFamilyMember
            {
                ProductId = member.ProductId,
                VariantLabel = member.VariantLabel,
                SortOrder = index
            })
            .ToList();

    /// <summary>
    /// Whether the family already holds exactly the declared members, labels and order.
    /// </summary>
    private static bool AlreadyMatches(ProductFamily family, List<ProductFamilyMemberRequest> declared)
    {
        var current = family.Members.OrderBy(member => member.SortOrder).ToList();

        return current.Count == declared.Count
            && current.Zip(declared).All(pair =>
                pair.First.ProductId == pair.Second.ProductId
                && pair.First.VariantLabel == pair.Second.VariantLabel);
    }

    /// <summary>
    /// Rejects the declaration when any product already belongs to a different family.
    /// </summary>
    /// <remarks>
    /// The unique index is what actually guarantees single membership; this read exists so the
    /// rejection can name the products and the families holding them. Both are needed: without the
    /// index the guarantee has a race in it, and without the read the caller gets a constraint
    /// violation it cannot act on.
    /// </remarks>
    private async Task GuardAgainstOtherFamiliesAsync(
        List<ProductFamilyMemberRequest> declared,
        Guid familyId)
    {
        if (declared.Count == 0)
        {
            return;
        }

        var clashes = await _familyRepository.GetMembershipsInOtherFamiliesAsync(
            declared.Select(member => member.ProductId), familyId);

        if (clashes.Count == 0)
        {
            return;
        }

        throw new ProductFamilyConflictException(
            clashes
                .Select(clash => new ProductFamilyConflictDto(
                    clash.ProductId,
                    clash.ProductFamilyId,
                    clash.Family?.Name ?? string.Empty))
                .ToList());
    }

    /// <summary>PostgreSQL's SQLSTATE for a unique-constraint violation.</summary>
    private const string UniqueViolationSqlState = "23505";

    /// <summary>
    /// Saves, turning a lost race for a product into the same conflict a pre-check would have found.
    /// </summary>
    /// <remarks>
    /// The window is small but real: two administrators can declare the same product into two
    /// families between the guard's read and this write. Letting the violation escape would surface
    /// as a 500 for what is an ordinary conflict, so it is re-read and reported the same way — the
    /// caller cannot tell which of the two paths rejected it, which is the point.
    /// </remarks>
    private async Task SaveTranslatingMembershipRaceAsync(List<ProductFamilyMemberRequest> declared)
    {
        try
        {
            await _unitOfWork.SaveChangesAsync();
        }
        catch (DbUpdateException exception) when (IsUniqueViolation(exception))
        {
            _logger.LogInformation(
                "product_family_membership_lost_race {ProductIds}",
                string.Join(",", declared.Select(member => member.ProductId)));

            // Read with no family excluded: by now the winning membership is committed, so the
            // products that clash are exactly the ones the other writer took.
            var clashes = await _familyRepository.GetMembershipsInOtherFamiliesAsync(
                declared.Select(member => member.ProductId), Guid.Empty);

            throw new ProductFamilyConflictException(
                clashes
                    .Select(clash => new ProductFamilyConflictDto(
                        clash.ProductId,
                        clash.ProductFamilyId,
                        clash.Family?.Name ?? string.Empty))
                    .ToList());
        }
    }

    /// <summary>
    /// Whether a persistence failure is a unique index refusing a duplicate.
    /// </summary>
    /// <remarks>
    /// Matched on the SQLSTATE rather than on the message, which the server localises. Read through
    /// <see cref="DbException.SqlState"/>, a base-library property, so the application layer stays
    /// free of a reference to the PostgreSQL driver.
    /// </remarks>
    private static bool IsUniqueViolation(DbUpdateException exception) =>
        exception.InnerException is DbException { SqlState: UniqueViolationSqlState };

    // ── Mapping ───────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Re-reads a family after writing, so the response carries what the database actually holds.
    /// </summary>
    private async Task<ProductFamilyDto> ReadBackAsync(Guid id)
    {
        var family = await _familyRepository.GetWithMembersAsync(id);
        return await MapAsync(family!);
    }

    /// <summary>
    /// Maps a family and resolves the SKU and name of each member's product.
    /// </summary>
    /// <remarks>
    /// Resolved in one query rather than per member. There is no navigation property from the
    /// membership to the product — the catalogue is deliberately not traversable into this — so the
    /// products are fetched by identifier and joined here.
    /// </remarks>
    private async Task<ProductFamilyDto> MapAsync(ProductFamily family)
    {
        var ordered = family.Members.OrderBy(member => member.SortOrder).ToList();
        var productIds = ordered.Select(member => member.ProductId).ToList();

        var products = await _productRepository.GetAll()
            .Where(product => productIds.Contains(product.Id))
            .Select(product => new { product.Id, product.SKU, product.Name })
            .ToListAsync();

        var byId = products.ToDictionary(product => product.Id);

        var members = ordered
            .Select(member =>
            {
                var found = byId.TryGetValue(member.ProductId, out var product);
                return new ProductFamilyMemberDto(
                    member.ProductId,
                    found ? product!.SKU : string.Empty,
                    found ? product!.Name : string.Empty,
                    member.VariantLabel,
                    member.SortOrder);
            })
            .ToList();

        return new ProductFamilyDto(
            family.Id,
            family.Name,
            family.Description,
            family.Origin.ToString(),
            members);
    }
}
