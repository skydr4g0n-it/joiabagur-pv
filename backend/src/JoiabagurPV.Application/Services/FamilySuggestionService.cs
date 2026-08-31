using JoiabagurPV.Application.DTOs.Ai;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using Microsoft.Extensions.Logging;

namespace JoiabagurPV.Application.Services;

/// <summary>
/// Assisted family grouping: jbg-ai proposes, this side persists.
/// </summary>
/// <remarks>
/// <para>
/// The split is not stylistic. Only <see cref="IProductFamilyService"/> stamps
/// <c>Product.UpdatedAt</c> on the products entering and leaving a family, and that timestamp is
/// the cursor the catalog indexing feed reads. Writing the membership rows any other way — a
/// direct <c>INSERT</c> from the Python side, say — leaves the incremental pull blind to them,
/// and leaves it blind without raising anything at all: the index would simply keep reporting no
/// families forever.
/// </para>
/// <para>
/// Proposing and applying are two calls because the proposal is not persisted anywhere. The
/// caller returns the subset it accepts, so there is no suggestion store to keep in step with the
/// catalog and nothing that can go stale between the two.
/// </para>
/// </remarks>
public class FamilySuggestionService(
    IAiGatewayClient gateway,
    IProductFamilyService familyService,
    ILogger<FamilySuggestionService> logger) : IFamilySuggestionService
{
    private readonly IAiGatewayClient _gateway = gateway;
    private readonly IProductFamilyService _familyService = familyService;
    private readonly ILogger<FamilySuggestionService> _logger = logger;

    /// <inheritdoc/>
    public async Task<AiFamilySuggestResponse> SuggestAsync(
        FamilySuggestionsRequest request,
        Guid userId,
        string role,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        var scope = AiCallScope.ForCatalog(userId, role);
        var response = await _gateway.SuggestFamiliesAsync(
            new AiFamilySuggestRequest { PieceType = request.PieceType },
            scope,
            cancellationToken);

        // Logged together because a run that proposes little because it refused much is a
        // catalog finding, and reading the proposal count alone would hide it.
        _logger.LogInformation(
            "family_suggestions_read {Proposals} {Rejected} {Excluded} {AlreadyInFamily}",
            response.Proposals.Count,
            response.RejectedGroups.Count,
            response.ExcludedProducts.Count,
            response.AlreadyInFamilyCount);

        return response;
    }

    /// <inheritdoc/>
    public async Task<ApplyFamilySuggestionsResponse> ApplyAsync(
        ApplyFamilySuggestionsRequest request,
        Guid approvedByUserId)
    {
        ArgumentNullException.ThrowIfNull(request);

        var result = new ApplyFamilySuggestionsResponse();

        foreach (var family in request.Families)
        {
            var declaration = new CreateProductFamilyRequest
            {
                Name = family.Name,
                Description = family.Description,
                Members = [.. family.Members.Select(member => new ProductFamilyMemberRequest
                {
                    ProductId = member.ProductId,
                    VariantLabel = member.VariantLabel
                })]
            };

            try
            {
                var created = await _familyService.CreateFromSuggestionAsync(
                    declaration, approvedByUserId);

                result.FamiliesCreated++;
                result.MembersCreated += created.Members.Count;
            }
            catch (ProductFamilyConflictException conflict)
            {
                // One contested product must not cost the administrator the other hundred and
                // fifty approvals. The family is skipped whole — never half-created — and named
                // in the response together with whoever holds its products.
                result.Conflicts.Add(new FamilyApplyConflictDto
                {
                    FamilyName = family.Name,
                    Conflicts = [.. conflict.Conflicts]
                });

                _logger.LogWarning(
                    "family_suggestion_conflict {FamilyName} {ConflictCount}",
                    family.Name,
                    conflict.Conflicts.Count);
            }
        }

        _logger.LogInformation(
            "family_suggestions_applied {FamiliesCreated} {MembersCreated} {Conflicts} {ApprovedBy}",
            result.FamiliesCreated,
            result.MembersCreated,
            result.Conflicts.Count,
            approvedByUserId);

        return result;
    }
}
