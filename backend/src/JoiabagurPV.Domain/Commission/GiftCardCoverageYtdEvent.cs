namespace JoiabagurPV.Domain.Commission;

public sealed record GiftCardCoverageYtdEvent(
    DateTime EntryDateUtc,
    DateTime CreatedAtUtc,
    decimal Amount);
