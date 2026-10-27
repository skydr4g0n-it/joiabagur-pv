# Tasks

## 1. Schema and seed

- [x] 1.1 Add `SystemProductKind`, `GiftCard`, `GiftCardCoverageEntry` (Apply/Release), and `GiftCardReassignment` with 18,2 amounts and a unique `GC-` code index. Verify with `dotnet build` on the backend and a migration that applies on a clean database.
- [x] 1.2 Seed product `SYS-GIFT-CARD` and payment method `GIFT_CARD` assigned to every POS, and reject deactivation. Verify `PaymentMethodServiceTests` / seed test `Seed_GiftCardMethod_IsHiddenAndNotDeactivatable`.
- [x] 1.3 Exclude system products from catalog, search, Excel import, and recognition. Verify `ProductServiceTests.Search_SystemProductSku_ReturnsEmpty` and an import test that reports the system SKU as an error.
- [x] 1.4 Update `Documentos/modelo-de-datos.md` with the new entities and the rule that issuance `Sale.Price` is not reduced. Verify the new tables and fields are named as in the migration.

## 2. Issuance

- [x] 2.1 Implement `POST /api/gift-cards` for admin and assigned operators: preset or free face value, expiry strictly after today UTC, optional holder, normal POS payment method, sale of the system product with no inventory movement, idempotency key. Verify `GiftCardServiceTests.Issue_PresetOnAssignedPos_CreatesSaleAndDoesNotMoveStock`, `Issue_UnassignedPos_ReturnsForbidden`, `Issue_ExpiryToday_ReturnsBadRequest`, and `Issue_SameIdempotencyKey_DoesNotDuplicate`.
- [x] 2.2 Implement paginated list (max 50) and detail with nominal, spendable balance, accounted remainder, links, and operations, plus admin reassignment that keeps the issuance sale on the original POS. Verify `List_Operator_OmitsOtherPos` and `Reassign_Admin_WritesHistoryAndKeepsIssuancePos`.
- [x] 2.3 Add the Spanish card list, issue form, and detail screen in Metronic, including Code128 via `frontend/src/lib/code128.ts` and a QR from `QrCodeService`. Verify component test `should show nominal and code when issuance succeeds` and `npm test` for that file.

## 3. Redemption

- [x] 3.1 Extend `CreateBulkSalesRequest` with gift card codes and allocate cheapest line first, then card order, inside the existing bulk transaction. A card that covers nothing stays unused; the first apply sets spendable balance to 0. Verify `SalesServiceTests` for the 50 EUR, 150 EUR, 50+150 EUR, 150+200 EUR, and 50+30 EUR cases, named `Redeem_Example*_ExpectedCoverage`.
- [x] 3.2 Reject expired, wrong-POS, already used, accounted-remainder-only reuse, and inactive remainder payment methods; reject bulk lines for system products. Keep bulk `Idempotency-Key` from creating a second apply. Verify `Redeem_ExpiredCard_LeavesBalanceUnchanged`, `Redeem_WrongPos_ReturnsBadRequest`, `Redeem_AlreadyUsed_ReturnsBadRequest`, `Redeem_AccountedRemainderOnly_ReturnsBadRequest`, `Redeem_SameIdempotencyKey_DoesNotDuplicate`, and `CreateBulk_SystemProductLine_ReturnsBadRequest`.
- [x] 3.3 Put `GiftCardCoverageAmount` on sale history. Verify `GetHistory_CoveredSale_IncludesCoverageAmount`.
- [x] 3.4 Add checkout UI to attach cards and scan `GC-` codes without a product lookup, showing immediate errors for expired, wrong-POS, and already-used cards, using one remainder method or `GIFT_CARD` when nothing is due. Verify `should add the card when the scanner decodes a GC code`, `should show an error when the scanner decodes an expired GC code`, and a Playwright spec that issues a 100 EUR card and sells a 150 EUR product, asserting 50 EUR still due.

## 4. Exchange and classic returns

- [x] 4.1 Implement `POST /api/gift-cards/{id}/exchanges`: multiple linked lines per request, full-price returns, same-day releases, new sales, cheapest-first apply capped by the accounted remainder, excess charged with one POS method, returned products stay linked, same product rejected, 30 days from the product sale date, expiry does not block an in-window exchange, idempotency key. Verify `Exchange_UpgradeInsideRemainder_ChargesNothing`, `Exchange_UpgradeBeyondRemainder_ChargesExcess`, `Exchange_Downgrade_RestoresAccountedValueOnly`, `Exchange_MultipleLines_OneRequest`, and `Exchange_SameIdempotencyKey_DoesNotDuplicate`.
- [x] 4.2 Reject classic returns of covered sales and issuance sales; omit both from eligible sales. Verify `CreateReturn_GiftCardLinkedSale_ReturnsBadRequest`, `CreateReturn_IssuanceSale_ReturnsBadRequest`, `GetEligible_CoveredSale_IsOmitted`, and `GetEligible_IssuanceSale_IsOmitted`.
- [x] 4.3 Add the Spanish exchange screen for admin and operator. Verify Playwright exchanges a linked product for a more expensive one and shows the cash excess, and a component test `should block the classic return action when the sale is linked to a gift card`.

## 5. Revenue, dashboard, and commission

- [x] 5.1 Subtract apply and add release by date in sales-report `totalAmount`, dashboard today/week/month/trend/POS bars, and payment-mix amounts for sales that have no return. Do not put a returned sale back into the mix. Verify `SalesReport_CoverageOnRedemptionDay_NetsCashTopUp` (100 EUR card on 1 March, 150 EUR product and 100 EUR apply on 15 March, report for 15 March equals 50 EUR) and `Dashboard_ReturnedCoveredSale_IsAbsentFromPaymentMix`.
- [x] 5.2 Feed the same economic amount into `SaleReportLine` and commission events, including issuance at nominal and a covered product at gross minus apply. Verify `ComputeCommission_CoveredProduct_UsesCashPortion` and that an uncovered jewelry sale still uses `Price × Quantity`.
- [x] 5.3 Update `Documentos/epicas.md`, the EP3/EP5 stories, and the operator guide in Spanish for issue, redeem, and exchange. Verify those files mention face value, single use, and exchange-only returns.

## Workflow follow-up

- Implementation starts only when someone runs `/opsx-apply` or asks to apply this change.
- Archive only after the specs are synced and `Documentos/` matches what shipped.
