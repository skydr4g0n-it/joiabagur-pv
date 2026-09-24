/**
 * Sale Card Copy Table (EP15 / C36)
 *
 * The backend sends codes; the Spanish a human reads is written here. That split is the rule the
 * assisted search panel's living spec already states for the retriever's match reasons, and the
 * AI service's own vocabulary module states it back from the other side: *"codes on the wire and
 * copy in the presentation layer"*.
 *
 * A module of its own, exported and tested directly, following `ORIGIN_LABELS`/`originLabel` of
 * C16 — not literals scattered through the components. The reason is not tidiness: the warning
 * vocabulary is **closed but versioned**, and a neutral fallback for a value this screen does not
 * know is the only thing standing between a new version of the service and a broken row.
 */

import type { PitchStatus, SubstitutesOutcome } from '@/types/sales-assist.types';

/* -------------------------------------------------------------------------------------------
 * Warnings
 * ---------------------------------------------------------------------------------------- */

/**
 * The missing-size-label code, named because the card treats it differently from every other
 * warning: it is rendered as an attribute of the piece beside its SKU and never as an alert.
 *
 * It fires on **58,3 %** of cards and is almost perfectly anti-correlated with belonging to a
 * family — **4,0 %** with one against **92,5 %** without one — so it states the enrichment status
 * of the catalog rather than a fact about the piece in front of the customer. Rendered as an
 * alert it would crowd out `stock_critical`, which fires on 3,9 % and is the one that can cost a
 * sale.
 *
 * It is **never suppressed**: the frontend does not remove a code the backend emitted.
 */
export const SIZE_LABEL_MISSING = 'size_label_missing';

/**
 * The Spanish for each warning code the two routes of C34 can emit.
 *
 * Five entries, and five is the whole reachable vocabulary. The two router refusal codes —
 * `query_out_of_domain` and `query_not_in_catalogue` — deliberately have **no row here**: the AI
 * service's intent classifier runs only in the free-query mode and both of these routes are
 * always anchored, so neither can arrive. Writing their Spanish would buy two green tests over
 * impossible paths; instead they fall to the neutral label, and a test witnesses that.
 *
 * A lookup rather than a conditional, so a code added by a later version of the service is a new
 * entry here instead of a change to a component.
 */
const WARNING_LABELS: Record<string, string> = {
  family_has_variants: 'Esta pieza tiene otras variantes en esta tienda',
  stock_critical: 'Quedan pocas unidades',
  family_members_out_of_stock: 'Alguna variante de la familia está agotada aquí',
  knowledge_not_covered: 'La documentación no cubre esta pregunta',
  [SIZE_LABEL_MISSING]: 'Sin talla declarada',
};

/**
 * The label for a code this screen does not know.
 *
 * Neutral on purpose: it says that something was flagged without inventing what, which is the
 * honest thing to say about a value whose meaning this version does not hold. The raw code is
 * never shown — it is engineering vocabulary and means nothing at a counter.
 */
export const UNKNOWN_WARNING_LABEL = 'Aviso del catálogo';

/** The Spanish for a warning code, degrading to the neutral label rather than failing. */
export function warningLabel(code: string): string {
  return WARNING_LABELS[code] ?? UNKNOWN_WARNING_LABEL;
}

/** Whether this screen holds a translation for a code, for the tests that assert the fallback. */
export function isKnownWarning(code: string): boolean {
  return code in WARNING_LABELS;
}

/**
 * The warnings that belong in the alert block: everything the backend emitted except the
 * missing-size-label code, which the header renders as an attribute of the piece.
 *
 * The order is the one received. Nothing is added and nothing is removed.
 */
export function alertWarnings(warnings: readonly string[]): string[] {
  return warnings.filter((code) => code !== SIZE_LABEL_MISSING);
}

/* -------------------------------------------------------------------------------------------
 * The state of the argument
 * ---------------------------------------------------------------------------------------- */

/**
 * What the card says about an argument it was not given.
 *
 * `action` is never empty. A message that only states an absence is a dead end for someone
 * standing at a counter with a customer; an honest abstention says what would be needed to get
 * past it.
 */
export interface PitchMessage {
  /** The state itself, so two states that share a text stay distinguishable in the document. */
  status: PitchStatus;
  title: string;
  body: string;
  /** What to do next. */
  action: string;
}

/**
 * Six states, five renderings: `generated` paints the argument, and the other five share four
 * texts between them.
 *
 * **`ai_unavailable` and `not_generated` do not share a message**, however similar they sound.
 * In the first, half the screen is pure catalog — no citations, no match reasons, and the family
 * read from the transactional catalog rather than from the index. In the second the piece's data
 * is the index's, intact. One message for both would make the card misstate where what it is
 * showing came from, which is the one thing the screen must never do.
 *
 * **The two withheld states do share a message**, because nothing the operator can do differs
 * between them. They remain distinguishable in the document through `status`.
 */
const PITCH_MESSAGES: Record<Exclude<PitchStatus, 'generated'>, Omit<PitchMessage, 'status'>> = {
  ai_unavailable: {
    title: 'El asistente no está disponible',
    body: 'Lo que ves viene del catálogo: el precio, las unidades y las variantes son reales, pero no hay argumentario ni fuentes.',
    action: 'Puedes vender con estos datos, o volver a pedir la ficha en un momento.',
  },
  not_generated: {
    title: 'El argumentario no se ha generado',
    body: 'Los datos de la pieza son los del índice y están completos; sólo falta el texto.',
    action: 'Vuelve a pedir la ficha, o pregunta algo concreto sobre la pieza.',
  },
  withheld_by_ai: {
    title: 'Sin argumentario para esta pieza',
    body: 'No he podido redactar algo que pueda sostener con los datos de esta pieza.',
    action: 'Pregunta algo concreto sobre ella y te contesto con las fuentes que tenga.',
  },
  withheld_unresolved: {
    title: 'Sin argumentario para esta pieza',
    body: 'No he podido redactar algo que pueda sostener con los datos de esta pieza.',
    action: 'Pregunta algo concreto sobre ella y te contesto con las fuentes que tenga.',
  },
  withheld_out_of_stock: {
    title: 'Esta pieza está agotada aquí',
    body: 'No redacto un argumentario de algo que no puedes vender hoy en esta tienda.',
    action: 'Te propongo alternativas que sí están disponibles.',
  },
};

/**
 * What to say about the state of the argument, or `null` when there is an argument to paint.
 *
 * An unknown state is treated as one without an argument rather than assumed to be `generated`:
 * claiming a text was delivered when the card does not know what happened would be the worse of
 * the two errors.
 */
/**
 * A piece the AI service could not process, which is not an outage (C40).
 *
 * It is the state of a piece added after the last index synchronisation — one the next
 * synchronisation fixes by itself, with nobody doing anything. Until the backend began reporting
 * why it degraded, this arrived looking exactly like a service that had fallen over, so the one
 * useful thing an operator could know — wait, or sell from the catalog and stop worrying — was
 * the one thing the screen could not say.
 */
const PRODUCT_NOT_INDEXED: Omit<PitchMessage, 'status'> = {
  title: 'Esta pieza todavía no está preparada',
  body: 'Es una pieza reciente y el asistente aún no la ha procesado. El precio, las unidades y las variantes que ves son reales y vienen del catálogo.',
  action: 'Puedes vender con estos datos. Estará lista sin que tengas que hacer nada.',
};

export function pitchMessage(status: PitchStatus, degradedReason?: string | null): PitchMessage | null {
  if (status === 'generated') return null;

  // Only refines the outage message, and only for this one reason. The other five — a switch, a
  // rejected credential, an unimplemented route, a genuine outage, an unclassified failure — all
  // mean the same thing to whoever is standing at the counter: the assistant is not answering.
  // This one does not, because it resolves itself and needs no action at all.
  if (status === 'ai_unavailable' && degradedReason === 'product_not_indexed') {
    return { status, ...PRODUCT_NOT_INDEXED };
  }

  const message = PITCH_MESSAGES[status as Exclude<PitchStatus, 'generated'>];
  if (!message) {
    return {
      status,
      title: 'Sin argumentario para esta pieza',
      body: 'No hay un texto que pueda enseñarte para esta pieza.',
      action: 'Los datos de la pieza que ves son reales; pregunta algo concreto si lo necesitas.',
    };
  }
  return { status, ...message };
}

/** Whether the citations are the sources of a text the operator can actually read. */
export function showsCitations(status: PitchStatus): boolean {
  return status === 'generated';
}

/* -------------------------------------------------------------------------------------------
 * Citations
 * ---------------------------------------------------------------------------------------- */

/** The scope value that marks a claim as a commitment of the house rather than a fact. */
export const ESTABLISHMENT_SCOPE = 'establecimiento';

/** Whether a citation states a commitment of the establishment. */
export function isEstablishmentClaim(claimScope: string): boolean {
  return claimScope === ESTABLISHMENT_SCOPE;
}

/**
 * The badge for a citation's scope.
 *
 * A commitment of the house and a fact of the world are not the same kind of claim, and passing
 * the first to a customer as if it were the second is how a shop ends up owing something it
 * never promised.
 */
export function claimScopeLabel(claimScope: string): string {
  return isEstablishmentClaim(claimScope) ? 'Compromiso de la casa' : 'Información general';
}

/** The sentence an establishment-scope citation carries, and a general one does not. */
export const ESTABLISHMENT_CLAIM_NOTE =
  'Conviene confirmarlo en tienda antes de trasladárselo a un cliente.';

/* -------------------------------------------------------------------------------------------
 * Substitutes
 * ---------------------------------------------------------------------------------------- */

/** What the card says about how a substitutes request ended. */
export interface SubstitutesMessage {
  outcome: SubstitutesOutcome;
  title: string;
  body: string;
}

/**
 * Four outcomes, four texts.
 *
 * `product_not_indexed` is **never** painted as an outage. It is a state of the catalog that the
 * next synchronisation fixes, and telling the operator the assistant is down would send them
 * chasing a problem that does not exist.
 */
const SUBSTITUTE_MESSAGES: Record<SubstitutesOutcome, Omit<SubstitutesMessage, 'outcome'>> = {
  ok: {
    title: 'Alternativas disponibles hoy',
    body: 'Piezas parecidas que esta tienda puede vender ahora mismo.',
  },
  none_in_stock: {
    title: 'Ninguna alternativa disponible hoy',
    body: 'He buscado piezas parecidas, pero ninguna tiene unidades en esta tienda.',
  },
  product_not_indexed: {
    title: 'Esta pieza aún no está preparada',
    body: 'Todavía no puedo buscarle alternativas parecidas. Se resuelve solo en la próxima sincronización del catálogo.',
  },
  ai_unavailable: {
    title: 'No he podido buscar alternativas',
    body: 'El asistente no está disponible en este momento.',
  },
};

/** What to say about a substitutes outcome, degrading rather than failing on an unknown one. */
export function substitutesMessage(outcome: SubstitutesOutcome): SubstitutesMessage {
  const message = SUBSTITUTE_MESSAGES[outcome];
  if (!message) {
    return {
      outcome,
      title: 'No he podido buscar alternativas',
      body: 'No hay alternativas que enseñarte para esta pieza.',
    };
  }
  return { outcome, ...message };
}

/**
 * Why no substitutes were asked for at all.
 *
 * Not one of the four outcomes: the request was never issued. With the AI path unavailable it
 * would come back `ai_unavailable` with certainty, so it is more honest to say so than to spend
 * it — but saying nothing would read as a piece with no alternatives, which is a different and
 * false claim.
 */
export const SUBSTITUTES_NOT_REQUESTED =
  'No busco alternativas porque el asistente no está disponible para esta ficha.';

/* -------------------------------------------------------------------------------------------
 * The question box
 * ---------------------------------------------------------------------------------------- */

/**
 * The five suggested questions, drawn from the counter situations the knowledge corpus covers:
 * wetting the piece, sensitive skin, cleaning it at home, a gift with no known size, and the
 * beach or the pool.
 *
 * Baking them into the interface is the remedy S4 prescribes — *"what to ask can be baked into
 * the interface"* — with a reason of its own that was measured rather than assumed: **9 of 40**
 * real counter questions fell into `knowledge_not_covered`, and showing what the corpus does
 * answer raises that coverage as well as being easier to use.
 *
 * Each maps onto a document that exists: `cuidados-generales`, `niquel-y-piel-sensible`,
 * `regalar-sin-saber-la-talla` and `joyas-playa-piscina-y-deporte`.
 */
export const SUGGESTED_QUESTIONS: readonly string[] = [
  '¿Se puede mojar esta pieza?',
  '¿Va bien para una piel sensible?',
  '¿Cómo se limpia en casa?',
  'Es un regalo y no sé la talla, ¿qué hago?',
  '¿Se puede llevar a la playa o a la piscina?',
] as const;

/** What the operator is told when the question is longer than the contract allows. */
export function questionTooLongMessage(max: number): string {
  return `La pregunta es demasiado larga: como mucho ${max} caracteres.`;
}
