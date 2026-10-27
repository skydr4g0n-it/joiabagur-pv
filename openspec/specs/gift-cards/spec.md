# gift-cards Specification

## Purpose
TBD - created by archiving change add-gift-cards. Update Purpose after archive.
## Requirements
### Requirement: Gift card issuance
The system SHALL let an admin or an operator issue one gift card as a sale of the system product at the chosen face value. The sale SHALL use a payment method assigned to the card's point of sale and SHALL NOT require manual price edit to be enabled. The sale SHALL NOT create an inventory movement.

#### Scenario: Operator issues a preset card
- **GIVEN** an operator assigned to POS A
- **AND** cash is an active payment method on POS A
- **WHEN** the operator issues a 100.00 EUR card on POS A paid in cash, with holder name "Ana"
- **THEN** the system stores a unique code, POS A, holder "Ana", nominal 100.00 EUR, and spendable balance 100.00 EUR
- **AND** creates a sale of the system product for 100.00 EUR on the current UTC date with payment method cash
- **AND** stock of every jewelry product is unchanged

#### Scenario: Operator cannot issue on an unassigned POS
- **GIVEN** an operator who is not assigned to POS B
- **WHEN** the operator tries to issue a card on POS B
- **THEN** the system rejects the request with 403 Forbidden
- **AND** does not create a card or a sale

### Requirement: Face value choices
The system SHALL accept only 50.00, 100.00, 150.00, or 200.00 EUR, or a free amount from 0.01 EUR to 99999.99 EUR with at most 2 decimal places.

#### Scenario: Reject an amount that is not allowed
- **GIVEN** an admin on a POS with an active payment method
- **WHEN** the admin submits a face value of 0.00 EUR
- **THEN** the system rejects the request with 400 Bad Request
- **AND** does not create a card

### Requirement: Card identity and expiry
The system SHALL store a system-generated code that starts with `GC-`, one point of sale, an optional holder name of at most 100 characters, and a mandatory expiry date. The nominal amount SHALL NOT change after issuance. At issuance the expiry date SHALL be strictly after the current UTC calendar date. For redemption, the card SHALL be valid through the end of that expiry UTC calendar day.

#### Scenario: Expiry date is required
- **GIVEN** an operator assigned to the target POS
- **WHEN** the operator submits an issuance without an expiry date
- **THEN** the system rejects the request with 400 Bad Request

#### Scenario: Reject expiry on or before today at issuance
- **GIVEN** an operator assigned to the target POS
- **AND** today's UTC calendar date is 2026-10-27
- **WHEN** the operator submits an issuance with expiry date 2026-10-27
- **THEN** the system rejects the request with 400 Bad Request
- **AND** does not create a card or a sale

#### Scenario: Redeem on the last valid UTC day
- **GIVEN** a card whose expiry date is today's UTC calendar date
- **AND** whose spendable balance equals the nominal amount
- **WHEN** an operator applies it at its current POS before the UTC day ends
- **THEN** the system accepts the redemption

### Requirement: Issuance idempotency
The system SHALL support idempotent `POST /api/gift-cards` using an `Idempotency-Key` so a retry does not create a second card or issuance sale.

#### Scenario: Retry issuance with the same idempotency key
- **GIVEN** a successful issuance that used an idempotency key
- **WHEN** the client repeats that request with the same key and the same body
- **THEN** the system returns the original result
- **AND** does not create another card or sale

### Requirement: Spendable balance never reactivates
After the issuance sale is linked to the card, the spendable balance SHALL NOT increase for any reason. Accounted remainder SHALL NOT become spendable on a later checkout.

#### Scenario: Accounted remainder cannot fund a new checkout
- **GIVEN** a 100.00 EUR card with spendable balance 0.00 EUR and accounted remainder 50.00 EUR after a partial redemption
- **WHEN** the operator applies that card on a new checkout at its current POS
- **THEN** the system rejects the request with 400 Bad Request
- **AND** the spendable balance stays 0.00 EUR

### Requirement: Accounted remainder
The system SHALL compute accounted remainder as `NominalAmount − (sum of Apply amounts − sum of Release amounts)` for that card. The detail and list SHALL expose this value alongside spendable balance.

#### Scenario: Partial redemption updates accounted remainder
- **GIVEN** a 100.00 EUR card with spendable balance 100.00 EUR
- **WHEN** a checkout covers a 50.00 EUR product with that card
- **THEN** the spendable balance is 0.00 EUR
- **AND** the accounted remainder is 50.00 EUR

### Requirement: Gift card list and trace
The system SHALL list cards with page size at most 50. Admins see every POS. Operators see only cards whose current POS is assigned to them. The detail SHALL show nominal, spendable balance, accounted remainder, linked products, coverage amounts, and operations.

#### Scenario: Operator list is limited to assigned POS
- **GIVEN** a card on POS A and a card on POS B
- **AND** the operator is assigned only to POS A
- **WHEN** the operator requests the first page of cards
- **THEN** the response includes the POS A card
- **AND** omits the POS B card
- **AND** returns at most 50 items

### Requirement: One spendable use per card at checkout
The system SHALL apply selected cards in operator order, covering checkout lines from the smallest line total (`Price × Quantity`) to the largest, keeping cart order on ties. A card that covers at least one cent SHALL end with spendable balance 0. A selected card that covers nothing SHALL stay fully spendable. Coverage SHALL be stored per product sale.

#### Scenario: Partial product leaves the unspent face value unsellable
- **GIVEN** a 100.00 EUR card with spendable balance 100.00 EUR
- **WHEN** a checkout covers a 50.00 EUR product with that card
- **THEN** coverage on that product sale is 50.00 EUR
- **AND** the spendable balance is 0.00 EUR
- **AND** a later checkout cannot apply the card

#### Scenario: Two products use the cheaper line first
- **GIVEN** a 100.00 EUR card
- **AND** a cart whose lines total 150.00 EUR and 50.00 EUR
- **WHEN** the checkout applies that card
- **THEN** coverage on the 50.00 EUR line is 50.00 EUR
- **AND** coverage on the 150.00 EUR line is 50.00 EUR
- **AND** the cash still due is 100.00 EUR

#### Scenario: More expensive lines stay fully cash
- **GIVEN** a 100.00 EUR card
- **AND** a cart whose lines total 150.00 EUR and 200.00 EUR
- **WHEN** the checkout applies that card
- **THEN** coverage on the 150.00 EUR line is 100.00 EUR
- **AND** coverage on the 200.00 EUR line is 0.00 EUR
- **AND** the cash still due is 250.00 EUR

#### Scenario: Several products fit under the face value
- **GIVEN** a 100.00 EUR card
- **AND** a cart whose lines total 50.00 EUR and 30.00 EUR
- **WHEN** the checkout applies that card
- **THEN** both lines are fully covered
- **AND** the cash still due is 0.00 EUR
- **AND** the spendable balance is 0.00 EUR

#### Scenario: A later selected card is not consumed when the first card covers the cart
- **GIVEN** two active 100.00 EUR cards and a cart totaling 50.00 EUR
- **WHEN** the operator selects both cards and the first card is applied first
- **THEN** the first card has spendable balance 0.00 EUR and coverage 50.00 EUR
- **AND** the second card still has spendable balance 100.00 EUR and no coverage

#### Scenario: Two cards share one cart by card order
- **GIVEN** two active 100.00 EUR cards and a cart whose lines total 150.00 EUR
- **WHEN** the operator selects both cards in that order and confirms checkout
- **THEN** the first card has spendable balance 0.00 EUR with coverage 100.00 EUR
- **AND** the second card has spendable balance 0.00 EUR with coverage 50.00 EUR
- **AND** the cash still due is 0.00 EUR

### Requirement: Redemption revenue dates
The system SHALL keep the issuance sale at its nominal amount and original date. Each product sale SHALL use the catalog price snapshot and the redemption date. Coverage SHALL be dated the redemption date and subtracted from that date's revenue. Stock SHALL decrease by the sold quantity once.

#### Scenario: Cash top-up is the only new revenue on redemption day
- **GIVEN** a 100.00 EUR card sold on 1 March
- **WHEN** on 15 March the customer takes a 150.00 EUR product and 100.00 EUR is covered by the card
- **THEN** the 1 March card sale is still 100.00 EUR
- **AND** the product sale is 150.00 EUR dated 15 March
- **AND** coverage of 100.00 EUR is dated 15 March
- **AND** 15 March net revenue from this checkout is 50.00 EUR
- **AND** all-time revenue from the card and the product is 150.00 EUR
- **AND** the product stock decreases by 1

#### Scenario: Fully covered product adds no net revenue
- **GIVEN** a 100.00 EUR card
- **WHEN** a checkout covers a 50.00 EUR product in full
- **THEN** that day's net revenue from the product and its coverage is 0.00 EUR
- **AND** all-time revenue remains 100.00 EUR

### Requirement: One remainder payment method
When cash is still due, every product line in the checkout SHALL use the same payment method, and that method SHALL be assigned and active on the POS. When nothing is due, every product line SHALL use the system payment method `GIFT_CARD`. The checkout SHALL be atomic and a repeated `Idempotency-Key` SHALL NOT create a second sale or a second coverage.

#### Scenario: Reject a remainder method that is not on the POS
- **GIVEN** a card that does not cover the cart
- **AND** the chosen remainder method is not active on that POS
- **WHEN** the operator confirms the checkout
- **THEN** the system rejects the request with 400 Bad Request
- **AND** does not change stock, sales, or the card

#### Scenario: Retry with the same idempotency key
- **GIVEN** a successful checkout that applied a gift card and used an idempotency key
- **WHEN** the client repeats that request with the same key and the same body
- **THEN** the system returns the original result
- **AND** does not create another sale or coverage

### Requirement: Expired, wrong-POS, and already-used cards
The system SHALL reject redemption when the card is expired, when the checkout POS is not the card's current POS, or when the spendable balance is 0.00 EUR.

#### Scenario: Expired card cannot be redeemed
- **GIVEN** a card whose expiry UTC calendar date is before today
- **AND** whose spendable balance is still the nominal amount
- **WHEN** an operator applies it at its current POS
- **THEN** the system rejects the request with 400 Bad Request
- **AND** the spendable balance is unchanged

#### Scenario: Wrong POS cannot redeem
- **GIVEN** a card on POS A with spendable balance equal to the nominal amount
- **AND** an operator whose checkout is on POS B
- **WHEN** the operator applies that card at POS B
- **THEN** the system rejects the request with 400 Bad Request
- **AND** the spendable balance is unchanged

#### Scenario: Already-used card cannot redeem again
- **GIVEN** a card whose spendable balance is 0.00 EUR after a prior redemption
- **WHEN** an operator applies that card at its current POS
- **THEN** the system rejects the request with 400 Bad Request
- **AND** the spendable balance stays 0.00 EUR

### Requirement: Issuance sale is not returnable
The system SHALL link each card to exactly one issuance sale. That issuance sale SHALL NOT be accepted by the classic product return flow.

#### Scenario: Classic return rejects the issuance sale
- **GIVEN** a gift card issuance sale with no gift-card coverage on that sale row
- **WHEN** the user submits that sale to the classic return endpoint
- **THEN** the system returns 400 Bad Request
- **AND** does not create a return or change stock

### Requirement: Gift card exchange records a return and new sales
The system SHALL exchange one or more linked product sales in a single request for one or more different products. Every new product SHALL differ from the product it replaces. It SHALL create returns and new product sales, keep returned products linked to the card, and require a return category.

#### Scenario: Exchange writes a return and keeps both products linked
- **GIVEN** a product sale linked to a gift card
- **WHEN** the user exchanges it for a different product at the same POS within 30 days and selects a return category
- **THEN** the system creates a return of the original sale and a sale of the new product
- **AND** both products stay linked to the card

#### Scenario: Reject exchange of the same product
- **GIVEN** a product sale linked to a gift card
- **WHEN** the user submits an exchange whose only new product is that same product
- **THEN** the system rejects the request with 400 Bad Request

#### Scenario: Exchange multiple linked lines in one request
- **GIVEN** two product sales linked to the same gift card at POS A
- **WHEN** the user exchanges both for two different products in one request at POS A within 30 days and selects a return category
- **THEN** the system creates a return for each original sale and a sale for each new product
- **AND** all four products stay linked to the card through coverage history

### Requirement: Exchange idempotency
The system SHALL support idempotent `POST /api/gift-cards/{id}/exchanges` using an `Idempotency-Key` so a retry does not create duplicate returns, sales, or coverage entries.

#### Scenario: Retry exchange with the same idempotency key
- **GIVEN** a successful exchange that used an idempotency key
- **WHEN** the client repeats that request with the same key and the same body
- **THEN** the system returns the original result
- **AND** does not create another return, sale, or coverage change

### Requirement: Exchange difference uses the accounted remainder
If the new total is higher, the system SHALL consume the accounted remainder first and charge only the excess with one POS payment method. If the new total is lower, the difference SHALL return to the accounted remainder and SHALL NOT increase the spendable balance.

#### Scenario: Upgrade inside the accounted remainder charges nothing
- **GIVEN** a 100.00 EUR card whose coverage on a linked 50.00 EUR product is 50.00 EUR
- **AND** the accounted remainder is 50.00 EUR and the spendable balance is 0.00 EUR
- **WHEN** the user exchanges that product for an 80.00 EUR product within 30 days at the same POS
- **THEN** the system creates a return of the 50.00 EUR sale and a new sale of 80.00 EUR
- **AND** coverage increases by 30.00 EUR
- **AND** the cash charged is 0.00 EUR
- **AND** the spendable balance stays 0.00 EUR
- **AND** both products remain linked to the card

#### Scenario: Upgrade beyond the accounted remainder charges the excess
- **GIVEN** a card with nominal 100.00 EUR, coverage 100.00 EUR, and accounted remainder 0.00 EUR linked to a 150.00 EUR product
- **WHEN** the user exchanges that product for a 180.00 EUR product
- **THEN** the cash charged is 30.00 EUR
- **AND** coverage stays 100.00 EUR

#### Scenario: Downgrade restores accounted value only
- **GIVEN** a 100.00 EUR card with coverage 50.00 EUR on a 50.00 EUR product and spendable balance 0.00 EUR
- **WHEN** the user exchanges that product for a 30.00 EUR product
- **THEN** coverage decreases by 20.00 EUR
- **AND** the accounted remainder increases by 20.00 EUR to 70.00 EUR
- **AND** the cash charged is 0.00 EUR
- **AND** the spendable balance stays 0.00 EUR
- **AND** the returned product stays linked to the card

### Requirement: Exchange window
The system SHALL allow the exchange only at the sale's POS and within 30 days of that product sale's date, including a partial quantity. Card expiry SHALL NOT block an exchange inside that window.

#### Scenario: Reject exchange after 30 days
- **GIVEN** a product sale linked to a gift card whose sale date is 31 days ago
- **WHEN** the user submits an exchange of that sale
- **THEN** the system rejects the request with 400 Bad Request

#### Scenario: Expiry does not block an in-window exchange
- **GIVEN** a card that expired after the product was sold
- **AND** the product sale date is within 30 days
- **WHEN** the user exchanges that product for a different product at the same POS
- **THEN** the system completes the exchange

### Requirement: POS reassignment
An admin SHALL be able to move a card to another POS. The issuance sale SHALL remain on the original POS. The system SHALL store the actor, the UTC timestamp, and the previous POS for each move. Operators SHALL NOT reassign cards.

#### Scenario: Admin reassignment keeps the issuance sale in place
- **GIVEN** a card issued on POS A
- **WHEN** an admin reassigns it to POS B
- **THEN** the card's current POS is POS B
- **AND** the issuance sale's POS is still POS A
- **AND** the history contains the admin, the timestamp, and POS A

#### Scenario: Operator cannot reassign
- **GIVEN** an operator assigned to both POS A and POS B
- **WHEN** the operator reassigns a card from POS A to POS B
- **THEN** the system rejects the request with 403 Forbidden

### Requirement: Printable and scannable code
The system SHALL render the card code as Code128 and as a QR from the issuance result. When the sales scanner decodes a value that starts with `GC-`, it SHALL resolve the card immediately. It SHALL add the card to checkout only when the card exists, is not expired, has spendable balance above 0.00 EUR, and its current POS matches the operator's checkout POS. A `GC-` value that does not match SHALL NOT be treated as a product SKU. The same attach, validation, coverage preview, remainder payment method, and checkout rules SHALL apply on the cart page and on the manual sale page.

#### Scenario: Attach a card on the manual sale page
- **GIVEN** an operator on the manual sale page with a product line totaling 150.00 EUR
- **AND** a 100.00 EUR card valid at that POS
- **WHEN** the operator enters or scans `GC-` on that page
- **THEN** the page shows the card attached
- **AND** the cash still due is 50.00 EUR
- **AND** confirming the sale applies the card through the same bulk checkout as the cart

#### Scenario: Scan a card code onto the checkout
- **GIVEN** a card whose code is `GC-ABC123` on the operator's current POS with spendable balance above 0.00 EUR and a valid expiry date
- **WHEN** the sales scanner decodes `GC-ABC123`
- **THEN** the checkout selects that gift card
- **AND** does not look up a product SKU

#### Scenario: Unknown gift card code
- **GIVEN** no card has code `GC-MISSING`
- **WHEN** the sales scanner decodes `GC-MISSING`
- **THEN** the system shows that the gift card was not found
- **AND** does not add a product line

#### Scenario: Scanner rejects an expired card immediately
- **GIVEN** a card whose expiry UTC calendar date is before today
- **WHEN** the sales scanner decodes that card's code at its current POS
- **THEN** the system shows that the gift card is expired
- **AND** does not add the card to checkout

#### Scenario: Scanner rejects a card on another POS immediately
- **GIVEN** a card on POS A with spendable balance above 0.00 EUR
- **AND** the operator's checkout POS is B
- **WHEN** the sales scanner decodes that card's code
- **THEN** the system shows that the gift card is not valid at this POS
- **AND** does not add the card to checkout

#### Scenario: Scanner rejects an already-used card immediately
- **GIVEN** a card whose spendable balance is 0.00 EUR
- **WHEN** the sales scanner decodes that card's code at its current POS
- **THEN** the system shows that the gift card was already used
- **AND** does not add the card to checkout

