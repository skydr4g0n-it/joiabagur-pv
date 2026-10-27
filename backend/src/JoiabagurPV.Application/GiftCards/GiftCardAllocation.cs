namespace JoiabagurPV.Application.GiftCards;

public sealed record GiftCardAllocationLineState(int LineIndex, decimal LineTotal, decimal Uncovered);

public sealed record GiftCardAllocationApply(int LineIndex, string CardCode, decimal Amount);

/// <summary>
/// Allocates gift card coverage cheapest line first, then card order.
/// </summary>
public static class GiftCardAllocation
{
    public static (List<GiftCardAllocationApply> Applies, List<string> CardsConsumed) Allocate(
        IReadOnlyList<GiftCardAllocationLineState> lines,
        IReadOnlyList<(string Code, decimal SpendableBalance)> cardsInOrder)
    {
        var lineStates = lines
            .Select(l => new MutableLineState(l.LineIndex, l.LineTotal, l.LineTotal))
            .ToList();

        var applies = new List<GiftCardAllocationApply>();
        var consumed = new List<string>();

        foreach (var card in cardsInOrder)
        {
            if (card.SpendableBalance <= 0)
                continue;

            var remainingOnCard = card.SpendableBalance;
            var appliedOnCard = 0m;

            foreach (var line in lineStates.OrderBy(l => l.LineTotal).ThenBy(l => l.LineIndex))
            {
                if (line.Uncovered <= 0 || remainingOnCard <= 0)
                    continue;

                var apply = Math.Min(line.Uncovered, remainingOnCard);
                if (apply <= 0)
                    continue;

                applies.Add(new GiftCardAllocationApply(line.LineIndex, card.Code, apply));
                line.Uncovered -= apply;
                remainingOnCard -= apply;
                appliedOnCard += apply;
            }

            if (appliedOnCard > 0)
                consumed.Add(card.Code);
        }

        return (applies, consumed);
    }

    private sealed class MutableLineState
    {
        public MutableLineState(int lineIndex, decimal lineTotal, decimal uncovered)
        {
            LineIndex = lineIndex;
            LineTotal = lineTotal;
            Uncovered = uncovered;
        }

        public int LineIndex { get; }
        public decimal LineTotal { get; }
        public decimal Uncovered { get; set; }
    }
}
