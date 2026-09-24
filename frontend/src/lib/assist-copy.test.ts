/**
 * Sale Card Copy Table Tests (EP15 / C36)
 *
 * Tested directly rather than through the components, following the pattern `originLabel` of C16
 * established. The substance is not "does it return a string": it is that the vocabulary is
 * closed **but versioned**, so a value this screen does not know has to degrade a row instead of
 * breaking the screen; and that two states of the argument which sound alike to an operator
 * describe different provenance and may never be merged.
 */

import { describe, it, expect } from 'vitest';

import {
  ESTABLISHMENT_CLAIM_NOTE,
  ESTABLISHMENT_SCOPE,
  SIZE_LABEL_MISSING,
  SUBSTITUTES_NOT_REQUESTED,
  SUGGESTED_QUESTIONS,
  UNKNOWN_WARNING_LABEL,
  alertWarnings,
  claimScopeLabel,
  isEstablishmentClaim,
  isKnownWarning,
  pitchMessage,
  questionTooLongMessage,
  showsCitations,
  substitutesMessage,
  warningLabel,
} from './assist-copy';
import type { PitchStatus, SubstitutesOutcome } from '@/types/sales-assist.types';

/** The five codes the two routes of C34 can actually emit. */
const REACHABLE_CODES = [
  'family_has_variants',
  'stock_critical',
  'family_members_out_of_stock',
  'knowledge_not_covered',
  SIZE_LABEL_MISSING,
];

/** The two the intent classifier emits, which runs only in the free-query mode. */
const ROUTER_REFUSAL_CODES = ['query_out_of_domain', 'query_not_in_catalogue'];

const ALL_STATUSES: PitchStatus[] = [
  'generated',
  'ai_unavailable',
  'not_generated',
  'withheld_by_ai',
  'withheld_unresolved',
  'withheld_out_of_stock',
];

describe('warningLabel', () => {
  it.each(REACHABLE_CODES)('should translate %s into Spanish a counter can read', (code) => {
    const label = warningLabel(code);

    expect(label).not.toBe(UNKNOWN_WARNING_LABEL);
    // The raw code is engineering vocabulary and means nothing at a counter.
    expect(label).not.toContain('_');
  });

  it('should cover exactly the five reachable codes and no more', () => {
    // Five is the whole reachable vocabulary. A sixth row here would be copy for a path that
    // cannot happen, which is the signature this project has been avoiding since C17.
    expect(REACHABLE_CODES.filter(isKnownWarning)).toHaveLength(5);
  });

  it('should label a router refusal code with the neutral fallback', () => {
    // These two are emitted only by the intent classifier, which runs only in the free-query
    // mode, and both routes of this screen are always anchored — so neither can arrive. Rather
    // than writing Spanish for an impossible path, the tolerance rule is what gets tested.
    for (const code of ROUTER_REFUSAL_CODES) {
      expect(isKnownWarning(code)).toBe(false);
      expect(warningLabel(code)).toBe(UNKNOWN_WARNING_LABEL);
    }
  });

  it('should fall back to a neutral label for an unknown warning code', () => {
    // The vocabulary is closed but versioned: this is the only thing that stops a new value
    // from a later service breaking a row of the screen.
    expect(warningLabel('a_code_from_a_later_version')).toBe(UNKNOWN_WARNING_LABEL);
  });

  it('should never show the raw code for an unknown warning', () => {
    expect(warningLabel('some_unknown_code')).not.toContain('some_unknown_code');
  });
});

describe('alertWarnings', () => {
  it('should keep the missing size label out of the alert block', () => {
    // It fires on 58,3 % of cards and is anti-correlated with having a family (4,0 % against
    // 92,5 %), so it describes the state of the enrichment and not the piece. As an alert it
    // would crowd out stock_critical, which fires on 3,9 % and can cost a sale.
    expect(alertWarnings([SIZE_LABEL_MISSING, 'stock_critical'])).toEqual(['stock_critical']);
  });

  it('should not suppress any other code the backend emitted', () => {
    const emitted = ['family_has_variants', 'stock_critical', 'a_future_code'];

    // Removing a code the backend emitted is exactly what the panel's living spec forbids doing
    // with the retriever's match reasons.
    expect(alertWarnings(emitted)).toEqual(emitted);
  });

  it('should keep the order the backend delivered', () => {
    expect(alertWarnings(['stock_critical', 'family_has_variants'])).toEqual([
      'stock_critical',
      'family_has_variants',
    ]);
  });

  it('should still translate the missing size label, because it is shown as an attribute', () => {
    // Filtered out of the alert block, never out of the card: nothing the backend emitted is
    // suppressed.
    expect(warningLabel(SIZE_LABEL_MISSING)).toBe('Sin talla declarada');
  });
});

describe('pitchMessage', () => {
  it('should return no message when the argument was generated', () => {
    expect(pitchMessage('generated')).toBeNull();
  });

  it('should tell a degraded card from one whose argument was not generated', () => {
    const degraded = pitchMessage('ai_unavailable');
    const ungenerated = pitchMessage('not_generated');

    // In the first, half the screen is pure catalog — no citations, no match reasons, the family
    // read from the transactional catalog. In the second the piece's data is the index's,
    // intact. One message for both would misstate where what is shown came from.
    expect(degraded?.title).not.toBe(ungenerated?.title);
    expect(degraded?.body).not.toBe(ungenerated?.body);
    expect(degraded?.body).toContain('catálogo');
  });

  it('should tell a piece that is not indexed from an unavailable service', () => {
    const notIndexed = pitchMessage('ai_unavailable', 'product_not_indexed');
    const outage = pitchMessage('ai_unavailable', 'ai_unavailable');

    // Same pitch status, opposite situations: one resolves itself with the next index
    // synchronisation and needs nobody to do anything; the other is a fault. Reading the first
    // as the second is what sent people looking for a problem that was not there.
    expect(notIndexed?.title).not.toBe(outage?.title);
    expect(notIndexed?.title).toContain('todav');
    expect(notIndexed?.action).toContain('sin que tengas que hacer nada');
  });

  it('should fall back to the unavailable message for a degraded reason it does not know', () => {
    const known = pitchMessage('ai_unavailable', 'ai_unavailable');
    const unknown = pitchMessage('ai_unavailable', 'invented_by_a_later_change');

    // Five of the six reasons mean the same thing at the counter, so an unrecognised one lands
    // on that message rather than on a blank or on a code the operator cannot read.
    expect(unknown).toEqual(known);
  });

  it('should keep the unavailable message when no reason is reported', () => {
    expect(pitchMessage('ai_unavailable')).toEqual(pitchMessage('ai_unavailable', null));
  });

  it('should share one text between the two withheld states', () => {
    const byAi = pitchMessage('withheld_by_ai');
    const unresolved = pitchMessage('withheld_unresolved');

    // Nothing the operator can do differs between them, so one text is honest.
    expect(byAi?.body).toBe(unresolved?.body);
    expect(byAi?.title).toBe(unresolved?.title);
  });

  it('should keep the two withheld states distinguishable even while sharing a text', () => {
    // The shared text is a presentation decision; the states are still two, and a test has to
    // be able to separate them.
    expect(pitchMessage('withheld_by_ai')?.status).toBe('withheld_by_ai');
    expect(pitchMessage('withheld_unresolved')?.status).toBe('withheld_unresolved');
  });

  it('should render the six states as five distinct renderings', () => {
    const texts = new Set(
      ALL_STATUSES.map((status) => {
        const message = pitchMessage(status);
        return message ? `${message.title}|${message.body}` : '<the argument itself>';
      }),
    );

    expect(texts.size).toBe(5);
  });

  it('should say what to do next when the argument is withheld', () => {
    for (const status of ['withheld_by_ai', 'withheld_unresolved', 'withheld_out_of_stock'] as const) {
      const message = pitchMessage(status);

      // An honest abstention says what would be needed to get past it. A message that only
      // states an absence is a dead end for someone standing at a counter.
      expect(message?.action).toBeTruthy();
      expect(message?.action.length).toBeGreaterThan(10);
    }
  });

  it('should end every message for a state without an argument in an action', () => {
    for (const status of ALL_STATUSES.filter((s) => s !== 'generated')) {
      expect(pitchMessage(status)?.action).toBeTruthy();
    }
  });

  it('should announce the alternatives when the piece has no stock', () => {
    const message = pitchMessage('withheld_out_of_stock');

    expect(message?.title).toContain('agotada');
    expect(message?.action).toContain('alternativas');
  });

  it('should treat an unknown state as one without an argument', () => {
    // Claiming a text was delivered when the card does not know what happened is the worse of
    // the two errors.
    const message = pitchMessage('a_state_from_a_later_version' as PitchStatus);

    expect(message).not.toBeNull();
    expect(message?.action).toBeTruthy();
  });
});

describe('showsCitations', () => {
  it('should show citations only when the argument was delivered', () => {
    expect(showsCitations('generated')).toBe(true);

    // Showing the sources of a text the operator cannot read is decoration, and they would be
    // only the ones that argument used anyway.
    for (const status of ALL_STATUSES.filter((s) => s !== 'generated')) {
      expect(showsCitations(status)).toBe(false);
    }
  });
});

describe('claim scope', () => {
  it('should mark an establishment claim differently from a general one', () => {
    expect(claimScopeLabel(ESTABLISHMENT_SCOPE)).not.toBe(claimScopeLabel('general'));
    expect(isEstablishmentClaim(ESTABLISHMENT_SCOPE)).toBe(true);
    expect(isEstablishmentClaim('general')).toBe(false);
  });

  it('should tell the operator to confirm a commitment of the house in store', () => {
    // A commitment of the house and a fact of the world are not the same kind of claim, and
    // passing the first on as the second is how a shop owes something it never promised.
    expect(ESTABLISHMENT_CLAIM_NOTE).toContain('confirmarlo en tienda');
  });

  it('should treat an unknown scope as general rather than as a commitment', () => {
    expect(isEstablishmentClaim('scope_from_a_later_version')).toBe(false);
  });
});

describe('substitutesMessage', () => {
  const OUTCOMES: SubstitutesOutcome[] = [
    'ok',
    'none_in_stock',
    'product_not_indexed',
    'ai_unavailable',
  ];

  it('should tell the four substitute outcomes apart', () => {
    const titles = new Set(OUTCOMES.map((o) => substitutesMessage(o).title));

    expect(titles.size).toBe(4);
  });

  it('should say a piece is not ready yet rather than calling it an outage', () => {
    const notIndexed = substitutesMessage('product_not_indexed');
    const unavailable = substitutesMessage('ai_unavailable');

    // A state of the catalog the next synchronisation fixes, not a fault. Told as an outage it
    // would send the operator chasing a problem that does not exist.
    expect(notIndexed.title).toContain('preparada');
    expect(notIndexed.title).not.toBe(unavailable.title);
    expect(notIndexed.body).not.toContain('no está disponible');
  });

  it('should say nothing has stock when the service answered and nothing survived', () => {
    expect(substitutesMessage('none_in_stock').body).toContain('unidades');
  });

  it('should degrade an unknown outcome rather than failing', () => {
    const message = substitutesMessage('an_outcome_from_a_later_version' as SubstitutesOutcome);

    expect(message.title).toBeTruthy();
    expect(message.body).toBeTruthy();
  });

  it('should explain a request that was never issued separately from the four outcomes', () => {
    const outcomeTexts = OUTCOMES.map((o) => substitutesMessage(o).body);

    // Not asking is a fifth thing. Saying nothing at all would read as a piece with no
    // alternatives, which is a different and false claim.
    expect(outcomeTexts).not.toContain(SUBSTITUTES_NOT_REQUESTED);
    expect(SUBSTITUTES_NOT_REQUESTED).toContain('no está disponible');
  });
});

describe('suggested questions', () => {
  it('should offer five questions drawn from the corpus', () => {
    expect(SUGGESTED_QUESTIONS).toHaveLength(5);
  });

  it('should cover the five counter situations the corpus documents', () => {
    const all = SUGGESTED_QUESTIONS.join(' ').toLowerCase();

    // Each maps onto a document that exists: cuidados-generales, niquel-y-piel-sensible,
    // regalar-sin-saber-la-talla and joyas-playa-piscina-y-deporte.
    expect(all).toContain('mojar');
    expect(all).toContain('piel sensible');
    expect(all).toContain('limpia');
    expect(all).toContain('talla');
    expect(all).toContain('playa');
  });

  it('should keep every suggestion within the limit the contract declares', () => {
    for (const question of SUGGESTED_QUESTIONS) {
      expect(question.length).toBeLessThanOrEqual(500);
    }
  });
});

describe('questionTooLongMessage', () => {
  it('should name the limit so the operator knows what to cut to', () => {
    expect(questionTooLongMessage(500)).toContain('500');
  });
});
