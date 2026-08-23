"""Derive canonical co-occurrence pairs from BulkOperationId only."""

from __future__ import annotations

from collections import defaultdict

from jbg_ai.data.world.records import CoOccurrenceRow, SaleRow


def derive_co_occurrence(sales: list[SaleRow]) -> list[CoOccurrenceRow]:
    grouped: dict[str, list[SaleRow]] = defaultdict(list)
    for sale in sales:
        if not sale.bulk_operation_id:
            continue
        grouped[sale.bulk_operation_id].append(sale)

    counts: dict[tuple[str, str], int] = defaultdict(int)
    last_seen: dict[tuple[str, str], str] = {}
    for lines in grouped.values():
        skus = sorted({line.sku for line in lines})
        if len(skus) < 2:
            continue
        stamp = max(line.occurred_at for line in lines)
        for index, left in enumerate(skus):
            for right in skus[index + 1 :]:
                pair = (left, right)
                counts[pair] += 1
                previous = last_seen.get(pair)
                if previous is None or stamp > previous:
                    last_seen[pair] = stamp

    return [
        CoOccurrenceRow(
            product_sku_a=left,
            product_sku_b=right,
            co_sales_count=counts[(left, right)],
            last_seen_at=last_seen[(left, right)],
        )
        for left, right in sorted(counts)
    ]
