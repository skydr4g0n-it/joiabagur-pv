# index-feed

## MODIFIED Requirements

### Requirement: POS availability feed is sparse, bucketed and capped at two hundred
The system SHALL expose `GET /api/ai/index-feed/pos-availability` as a sparse assignment feed. A page MUST contain at most 200 items. The client MUST NOT choose the page size. Active `Inventory` rows in the cursor window MUST be upserts. An inactive assignment whose `greatest(LastUpdatedAt, UpdatedAt)` falls in the cursor window MUST be a tombstone with `reason = unassigned` and body `{ kind, pointOfSaleId, productId, reason, at }`. `qtyBucket` MUST be `0` when `Quantity <= 0`, `1-2` when quantity is 1 or 2, and `3+` when quantity ≥ 3. The JSON MUST NOT include `quantity`. `isAssignedHint` MUST reflect `Inventory.IsActive`.

`sales30d` and `sales90d` MUST be `SUM(Sale.Quantity)` for that `(ProductId, PointOfSaleId)` over the 30 and 90 days preceding a **reference instant**, without subtracting returns. That instant MUST be the configured `IndexFeed:SalesAsOf` when it is set, and the current time otherwise, so an unset configuration preserves the previous behaviour. It MUST be reported on the page as `computedAsOf`, because a windowed figure whose clock is not declared cannot be reproduced: the same configuration and seed must yield the same aggregates on different days. `lastSaleAt` MUST be `MAX(SaleDate)` or null. The cursor MUST be keyset on `(watermark, Inventory.Id)`. `PaginationConstants.MaxPageSize` and the operator product-list cap of 50 MUST NOT be used on this route.

#### Scenario: The feed returns a bucket not an exact quantity
- **GIVEN** an active inventory whose `Quantity` is 0, 1, 2 or ≥ 3
- **WHEN** `GET /api/ai/index-feed/pos-availability` is requested
- **THEN** `qtyBucket` is `0`, `1-2` or `3+` respectively
- **AND** the JSON does not include `quantity`
- **AND** `isAssignedHint` reflects `Inventory.IsActive`
- **AND** `sales30d` and `sales90d` sum `Sale.Quantity` in each window without subtracting returns

#### Scenario: A configured reference instant anchors the sales windows
- **GIVEN** `IndexFeed:SalesAsOf` is configured and sales exist both inside and outside the 30 days preceding it
- **WHEN** the POS feed is requested
- **THEN** `sales30d` counts only the sales inside that window
- **AND** the same request issued on a later day returns the same aggregates
- **AND** the page reports that instant as `computedAsOf`

#### Scenario: Without configuration the clock is the current time
- **GIVEN** `IndexFeed:SalesAsOf` is not configured
- **WHEN** the POS feed is requested
- **THEN** the windows are counted against the current time, as before
- **AND** `computedAsOf` reports the instant actually used

#### Scenario: Unassignment emits a tombstone
- **GIVEN** an inventory row whose `IsActive` is set to false
- **WHEN** the POS feed is queried with `since` earlier than that change
- **THEN** the item is emitted with `kind = tombstone` and `reason = unassigned`
- **AND** it is not emitted as an upsert

#### Scenario: The POS page cap is 200 and is not copied to UI lists
- **GIVEN** more than 200 availability rows
- **WHEN** the POS feed is requested without a cursor
- **THEN** the page contains at most 200 items
- **AND** `PaginationConstants.MaxPageSize` is not used
- **AND** the catalog feed remains capped at 50
