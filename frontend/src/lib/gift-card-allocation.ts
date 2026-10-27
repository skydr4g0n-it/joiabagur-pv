/**
 * Client-side mirror of backend cheapest-line-first gift card allocation.
 */

export interface AllocationLine {
  lineTotal: number;
}

export interface AttachedGiftCard {
  code: string;
  spendableBalance: number;
}

export function computeGiftCardCoverageTotal(
  lines: AllocationLine[],
  cards: AttachedGiftCard[],
): number {
  const lineStates = lines.map((l, index) => ({
    lineIndex: index,
    lineTotal: l.lineTotal,
    uncovered: l.lineTotal,
  }));

  let coverage = 0;

  for (const card of cards) {
    if (card.spendableBalance <= 0) continue;
    let remainingOnCard = card.spendableBalance;

    const sorted = [...lineStates].sort(
      (a, b) => a.lineTotal - b.lineTotal || a.lineIndex - b.lineIndex,
    );

    for (const line of sorted) {
      if (line.uncovered <= 0 || remainingOnCard <= 0) continue;
      const apply = Math.min(line.uncovered, remainingOnCard);
      if (apply <= 0) continue;
      line.uncovered -= apply;
      remainingOnCard -= apply;
      coverage += apply;
    }
  }

  return Math.round(coverage * 100) / 100;
}
