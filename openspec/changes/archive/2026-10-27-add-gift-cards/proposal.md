# Proposal

## Why

Operators and admins cannot sell a gift card or apply it when the customer later takes jewelry. The shop needs that sale recognized when the card is paid for, and product sales recognized at their real price, without counting the same money twice in inventory, dashboards, reports, or commissions.

## What Changes

- Issue a gift card as a sale of a system product at its face value. The sale does not move stock. Face value is chosen from 50, 100, 150, or 200 EUR, or entered as a free amount of at least 0.01 EUR with 2 decimal places.
- Each card has a unique system-generated code, one point of sale, an optional holder name, a mandatory expiry date strictly after the current UTC calendar date, an immutable nominal amount, and a spendable balance. Redemption is allowed through the end of the expiry UTC calendar day. No Customer entity.
- A card is spent in a single checkout. Coverage is applied cheapest line first (`Price × Quantity`, cart order on ties) and across cards in the order the operator selects. Any selected card that covers nothing stays unused. After a card covers any amount, its spendable balance becomes 0 and never increases again; the unspent face value becomes accounted remainder on the card (not spendable on a later checkout; only gift-card exchange can use it).
- Product lines stay normal sales at the catalog snapshot, dated the day the customer takes the product, and they decrement stock once. A dated coverage record subtracts the covered amount from revenue on that same day, so the day's net rises only by the cash still due. The original card sale stays at its nominal amount and original date. Example: a 100 EUR card on 1 March and a 150 EUR product on 15 March paid with 50 EUR by card produce day-15 net of 50 EUR and all-time revenue of 150 EUR.
- The cash remainder of a checkout uses one payment method assigned to the POS. Every product line in that checkout shares that method. When the cards cover the whole cart, every line shares a system payment method `GIFT_CARD` instead. Issuance uses a normal POS payment method and does not require `AllowManualPriceEdit`.
- Checkout that applies cards stays atomic and idempotent with the existing bulk-checkout key. Gift card issuance and exchange each use their own idempotency keys.
- The gift card issuance sale cannot use the classic return flow. Jewelry bought with a card cannot use classic return either. Those lines can only be exchanged in one request for one or more different products, at the same POS, within 30 days of the day the customer took that product, including a partial quantity. The exchange creates a normal return and new sales, so return KPIs move. Returned products stay linked to the card. If the new total is higher, the card's remaining accounted value (nominal minus coverage still applied) is consumed first and only the excess is charged with one POS payment method. If the new total is lower, the difference goes back to that accounted value and is not spendable.
- Expiry blocks a new redemption. It does not block an exchange of products already linked, which still follows the 30-day window.
- Admins can reassign a card to another POS from the card screen. The issuance sale stays on the original POS. Each reassignment stores who moved it, when, and the previous POS.
- Lists are paginated (max 50). The card screen shows nominal, spendable balance, accounted remainder (`nominal − net coverage applied`), linked products, and operations. Issuance can print a Code128 and a QR of the code; the sales scanner resolves `GC-` codes immediately and rejects expired, wrong-POS, or already-used cards before checkout.
- Revenue, sales reports, dashboard totals, and commission use the economic amount: card nominal plus cash collected later. Commission YTD uses that same amount, then the existing 21% VAT formula. Payment-method mix still drops any sale that has a return; for sales that remain, the method total excludes gift-card coverage on that sale.
- The system product is the first `SystemProductKind`. Other kinds are not implemented. It is hidden from catalog, search, import, and recognition, has no inventory row, and can be sold only through gift card issuance (not bulk checkout).

## Capabilities

### New Capabilities

- `gift-cards`: Issue, look up, redeem, expire, reassign, trace, and exchange gift cards, including the economic-amount rule that keeps revenue equal to cash collected.

### Modified Capabilities

- `product-management`: System products are stored and excluded from the jewelry catalog, search, import, and recognition.
- `payment-method-management`: Seed `GIFT_CARD`, assigned to every POS, hidden from ordinary sale payment choices, and not deactivatable.
- `sales-management`: Checkout accepts gift cards, records product sales at catalog price plus coverage, and does not move stock for the system product.
- `returns-management`: Classic returns reject jewelry with gift-card coverage and reject the gift card issuance sale. Exchange is the only return path for covered jewelry and still writes `Return` and new `Sale` rows.
- `sales-reports`: Aggregates and commission inputs use the economic amount (nominal plus later cash), not nominal plus full product price.
- `dashboard-analytics`: Today, week, month, and trend totals subtract gift-card coverage on the coverage date. Payment mix still omits sales that have any return.
- `pos-commission-tiers`: Year-to-date and the per-sale commission base use the economic amount for gift-card issuance, covered product sales, and their returns.

## Impact

- **Backend**: gift-card aggregate, coverage and exchange operations, system product and `GIFT_CARD` seed, checkout and return guards, report and dashboard and commission queries. New migration. Sale rows and inventory movements for jewelry stay as they are.
- **Frontend**: card management for admin and operator, checkout coverage on cart and manual sale, exchange flow, printable code, scanner lookup. UI copy in Spanish.
- **Database**: card, coverage, reassignment history. No Customer table. Issuance `Sale.Price` is never reduced.
- **Docs on apply**: `Documentos/epicas.md` (no gift-card story exists today; extend EP3 and EP5), `Documentos/modelo-de-datos.md`, and the affected guides. There is no EP for gift cards yet.
- **Tests**: service tests named `Method_Scenario_ExpectedResult`; UI tests named `should [behavior] when [condition]`; Playwright for issue, redeem, and exchange.

## Out of Scope

- A Customer master, voiding a card, reactivating spendable balance, classic return of the issuance sale, cash refund of a balance, and spending accounted remainder on a new checkout.
- Splitting the cash remainder across several payment methods.
- Keeping a returned sale inside the payment-method chart. That chart keeps today's rule and drops the whole sale.
- Expiry reminders, fiscal invoicing, and a VAT rate other than the existing 21% on the economic amount.
- Implementing further system-product kinds beyond the extension point.
- Moving the issuance sale when an admin reassigns the card.
