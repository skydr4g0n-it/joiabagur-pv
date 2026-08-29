## ADDED Requirements

### Requirement: Assisted search is an entry method of the sales flow, on its own route

The frontend SHALL expose assisted search as a third way of starting a sale, reachable from the sales landing page and living on its own lazily loaded route under the sales tree, alongside the scanning and manual entry routes.

The panel MUST hand the chosen product to the existing manual sale page through navigation state, the same mechanism the scanning and image recognition pages already use, rather than duplicating the payment method, quantity, price and stock logic that page already owns.

The panel MUST NOT replace or alter the SKU searcher of the manual sale page, which remains the fast path for an operator who already knows what they want.

#### Scenario: The panel is reachable from the sales landing page
- **WHEN** an authenticated operator opens the sales landing page
- **THEN** a third entry option for assisted search is displayed alongside scanning and manual entry
- **AND** activating it navigates to the assisted search route

#### Scenario: The chosen product is handed to the manual sale page
- **WHEN** the operator selects a result for sale
- **THEN** the application navigates to the manual sale page
- **AND** the chosen product identifier travels in navigation state
- **AND** the manual sale page pre-selects that product

#### Scenario: The pre-existing SKU searcher is untouched
- **WHEN** the manual sale page is used without passing through the panel
- **THEN** its SKU searcher behaves as it did before this capability existed

### Requirement: A search is issued only when the operator asks for one

The panel SHALL issue a search only on an explicit act — submitting the query field or activating the search control — and MUST NOT issue one as a side effect of typing, however long the pause between keystrokes.

Typing MUST NOT be debounced into requests. Every uncached search charges a query embedding and consumes the endpoint's per-user request budget, and the candidate cache is keyed on the whole query string, so no prefix of a query can ever hit it: a debounced field would spend several embeddings per query, of which at most one would be read.

The panel MUST offer a small set of example queries that fill the field and run the search in a single act, so that what the system can be asked is expressed by the interface rather than left for each operator to discover.

Quick filters MUST NOT issue a search on their own, since each change of filter produces a different cache key and would charge another embedding per toggled value.

Changing the point of sale MUST clear the displayed results and MUST NOT re-issue the search automatically, because the cache key includes the point of sale and the same query in another shop pays again.

#### Scenario: Typing costs nothing
- **WHEN** the operator types, deletes and types again without submitting
- **THEN** no search request is issued

#### Scenario: Submitting issues exactly one search
- **WHEN** the operator submits the query field or activates the search control
- **THEN** exactly one search request is issued

#### Scenario: An example query searches in one act
- **WHEN** the operator activates one of the example queries
- **THEN** the query field is filled with it
- **AND** exactly one search request is issued

#### Scenario: Toggling a filter does not search
- **WHEN** the operator toggles a quick filter
- **THEN** no search request is issued until the operator submits

#### Scenario: Changing the point of sale clears rather than re-searches
- **WHEN** the operator changes the point of sale after a search
- **THEN** the displayed results are cleared
- **AND** no search request is issued

### Requirement: Quick filters offer the closed vocabulary and can be cleared at once

The panel SHALL let the operator restrict a search by material, allowing several materials at the same time, and by piece category.

The material options MUST be the closed vocabulary the enrichment pipeline uses, and the panel MUST send the canonical term rather than the displayed label. A value outside that vocabulary matches nothing in the index and fails silently, so the list MUST be pinned by a test against its source of truth.

The panel MUST offer a single action that removes every active filter, because two hard filters — material at retrieval and point of sale at hydration — compose, and clearing them is the first remedy when a search returns nothing.

#### Scenario: Several materials at once
- **WHEN** the operator selects one material and then another
- **THEN** both remain selected
- **AND** the next search carries both

#### Scenario: The canonical term is what travels
- **WHEN** a material is selected
- **THEN** the search request carries its canonical vocabulary term

#### Scenario: Every filter can be removed in one act
- **WHEN** the operator activates the clear-filters action
- **THEN** no material or category filter remains active

### Requirement: The search is scoped to one point of sale, chosen according to role

The panel SHALL send a concrete point of sale on every search, taken from what the caller is allowed to use.

When the operator is assigned exactly one point of sale, it MUST be pre-selected and the selector MUST NOT be shown. When several are available, or the caller is an administrator, a selector MUST be offered. Only active points of sale MUST be offered, since the endpoint refuses an inactive one for every role.

#### Scenario: A single assignment needs no choice
- **WHEN** the operator is assigned exactly one point of sale
- **THEN** it is pre-selected
- **AND** no point-of-sale selector is displayed

#### Scenario: Several assignments are chosen from
- **WHEN** the caller has several points of sale available, or is an administrator
- **THEN** a selector is displayed with the active points of sale they may use

#### Scenario: A refused point of sale is reported as an access problem
- **WHEN** the endpoint refuses the search because the caller may not use that point of sale
- **THEN** the panel states that the caller has no access to that shop
- **AND** it does not present it as a failure of the search service

### Requirement: Results are displayed in the order received, with the truth the backend supplied

The panel SHALL render results in the exact order the backend returned them and MUST NOT sort, re-rank or filter them on the client, because the rank is the measurement of retrieval quality and re-sorting would make it measure the interface instead.

Each result MUST display its photo, SKU, name, price and the quantity at the point of sale of the search. A result with no stock MUST be displayed and marked as out of stock rather than hidden, since the shop carrying a piece it has run out of is an answer that can still save a sale.

Prices MUST be displayed in euros with Spanish locale formatting.

The result row MUST be an isolated component, so that the later change that adds the generated pitch, citations and family grouping extends it rather than rewriting the page.

#### Scenario: The order is the backend's
- **WHEN** results are rendered
- **THEN** they appear in the order the response listed them
- **AND** no client-side sorting is applied

#### Scenario: A result with no stock is shown and marked
- **WHEN** a result reports no stock at the point of sale
- **THEN** it is displayed
- **AND** it is marked as out of stock

### Requirement: A result explains itself with what the system actually knows

The panel SHALL explain a result with an origin badge derived from whether the assisted path served the search, together with the materials the retriever recognised.

The panel MUST NOT render the retriever's raw match reasons, which are a single constant value for every result until the lexical branch exists, and MUST NOT synthesise an explanation the system has not asserted.

The variant label MUST be displayed only when present, so that it appears on its own once the change that populates it has run, without the panel being touched.

The mapping from origin to badge MUST tolerate new values without a change to the panel, so that the lexical branch can contribute real reasons later.

#### Scenario: The badge and the materials explain the match
- **WHEN** a result is rendered
- **THEN** an origin badge is displayed
- **AND** the materials the retriever recognised are displayed

#### Scenario: The raw match reasons are not shown
- **WHEN** a result is rendered
- **THEN** the retriever's raw match reason values do not appear on screen

#### Scenario: An absent variant label leaves no gap
- **WHEN** a result carries no variant label
- **THEN** no size is displayed for it
- **AND** no placeholder value is invented

### Requirement: The four ways of showing nothing say four different things

The panel SHALL distinguish, on screen, the four situations that produce no results, because a single empty list would state something untrue in three of them:

- the retriever answered and nothing cleared its confidence threshold — the operator is invited to rephrase;
- the retriever returned candidates and none of them is carried by this shop — the operator is invited to clear the filters first, since a hard filter is the likelier cause than the wording;
- the assisted path did not serve the search, whether degraded or switched off — the operator is told that assisted search is not available and that what is shown comes from the text searcher;
- the request budget was exceeded — the operator is told there have been too many searches in a row.

Exceeding the request budget MUST NOT be presented as the AI service being unavailable. They have different causes, different remedies and opposite operational meanings: one is a fault, the other is the system protecting itself.

None of the four MUST be presented as an application error.

While a search is in flight the panel MUST show a loading state rather than an empty list.

#### Scenario: Abstention invites rephrasing
- **WHEN** the response reports the assisted path as available and the retrieval as low confidence, with no results
- **THEN** the panel states that nothing matching was found
- **AND** it invites the operator to rephrase

#### Scenario: An empty assortment invites clearing the filters
- **WHEN** the response reports the assisted path as available, the retrieval as not low confidence, candidates returned, and no results
- **THEN** the panel states that similar pieces exist but none is in this shop
- **AND** it offers clearing the filters as the first remedy

#### Scenario: An unavailable assisted path is named as such
- **WHEN** the response reports the assisted path as unavailable
- **THEN** the panel states that assisted search is not available
- **AND** it states that the results shown come from the text searcher

#### Scenario: An exhausted request budget is not an outage
- **WHEN** the endpoint answers that too many requests were made
- **THEN** the panel states that too many searches were made in a row
- **AND** it does not state that the assisted search service is unavailable

#### Scenario: A search in flight shows progress
- **WHEN** a search request is in flight
- **THEN** the panel shows a loading state
- **AND** it does not show an empty result list

### Requirement: A page shorter than requested is declared, not disguised

The panel SHALL state, when fewer results survived than the page size asked for, how many the shop has and how many candidates were considered, using the counters the response already carries.

This is the frequent case at the points of sale with the lowest assortment coverage. Left unsaid, it reads as the system being unable to search, when what happened is that the shop does not carry the assortment.

The results MUST still be displayed: a short page is not an error state.

#### Scenario: A short page explains itself
- **WHEN** fewer results survive than the requested page size, and at least one survives
- **THEN** the panel states how many results this shop has and how many candidates were considered
- **AND** the results are displayed normally

### Requirement: The retrieval funnel is visible to administrators only

The panel SHALL offer, to administrators only, a collapsed block carrying the correlation identifier and the candidate, survivor and displayed counts the response returns.

It MUST NOT be shown to operators, for whom it is noise, and MUST be collapsed by default.

#### Scenario: An administrator can inspect the funnel
- **WHEN** an administrator runs a search
- **THEN** a collapsed block with the correlation identifier and the three funnel counts is available

#### Scenario: An operator never sees the funnel
- **WHEN** an operator runs a search
- **THEN** no funnel block is displayed

### Requirement: One search episode per visit to the panel

The panel SHALL generate one search-episode identifier when it is opened and send it with every search of that visit, so that the reformulations of one visit group together and are not counted as abandoned queries.

Changing the point of sale within a visit MUST NOT change it. Opening the panel again MUST produce a new one, because two visits that each end in a selection are two legitimate episodes with nothing to group between them.

#### Scenario: Reformulations share the episode
- **WHEN** the operator searches several times within one visit
- **THEN** every request carries the same search-episode identifier

#### Scenario: Changing the shop does not start a new episode
- **WHEN** the operator changes the point of sale within one visit
- **THEN** the search-episode identifier is unchanged

#### Scenario: A new visit is a new episode
- **WHEN** the operator opens the panel again
- **THEN** a different search-episode identifier is generated

### Requirement: The selection is reported at the moment of the click and never blocks

The panel SHALL report the operator's selection to the telemetry endpoint at the instant of the click, without waiting for the outcome and without deferring or batching it, because the server stamps the moment and a delayed call would measure the browser instead of the operator.

A failure of that report MUST NOT show an error, MUST NOT block navigation and MUST NOT prevent the sale.

When the response carried no search event identifier — which the search endpoint is allowed to return — the report MUST be skipped silently.

#### Scenario: The report does not delay the operator
- **WHEN** the operator selects a result
- **THEN** the selection is reported
- **AND** navigation to the sale flow happens without waiting for its outcome

#### Scenario: A failed report is invisible
- **WHEN** reporting the selection fails
- **THEN** no error is shown to the operator
- **AND** navigation completed normally

#### Scenario: No event identifier means no report
- **WHEN** the search response carried no search event identifier
- **THEN** no selection report is issued
- **AND** the selection still works

### Requirement: The originating search travels with the product to the till

The panel SHALL pass the search event identifier along with the chosen product, and the sales flow MUST carry it, per line, from the selection through to sale creation — both when the sale is completed directly and when the line goes through the cart.

A sale started by any other entry method MUST carry no attribution and MUST remain valid.

#### Scenario: A direct sale carries its search
- **WHEN** the operator completes a sale directly after selecting a result
- **THEN** the sale creation request carries the search event identifier

#### Scenario: A cart line carries its own search
- **WHEN** the operator adds the selected product to the cart and checks out
- **THEN** that line of the bulk request carries its own search event identifier

#### Scenario: Another entry method carries none
- **WHEN** a sale is started by scanning or by SKU search
- **THEN** the sale creation request carries no search event identifier
- **AND** the sale is created normally

### Requirement: A stale response never overwrites a newer one

The panel SHALL ignore the response of any search that is no longer the current one, so that submitting, changing the point of sale and submitting again cannot leave the results of the first request on screen.

#### Scenario: An out-of-order response is discarded
- **WHEN** a second search is issued before the first has resolved
- **AND** the first response arrives last
- **THEN** the displayed results are those of the second search
