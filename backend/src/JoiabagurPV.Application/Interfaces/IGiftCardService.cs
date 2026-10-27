using JoiabagurPV.Application.DTOs.GiftCards;

namespace JoiabagurPV.Application.Interfaces;

public interface IGiftCardService
{
    Task<IssueGiftCardResult> IssueAsync(IssueGiftCardRequest request, Guid userId, bool isAdmin, string? idempotencyKey);

    Task<GiftCardListResponse> ListAsync(int page, int pageSize, Guid userId, bool isAdmin);

    Task<GiftCardDetailDto?> GetDetailAsync(Guid id, Guid userId, bool isAdmin);

    Task<(GiftCardByCodeDto? Card, string? ErrorMessage)> GetByCodeForPosAsync(string code, Guid pointOfSaleId);

    Task<ReassignGiftCardResult> ReassignAsync(Guid giftCardId, ReassignGiftCardRequest request, Guid userId, bool isAdmin);

    Task<ExchangeGiftCardResult> ExchangeAsync(
        Guid giftCardId,
        ExchangeGiftCardRequest request,
        Guid userId,
        bool isAdmin,
        string? idempotencyKey);
}
