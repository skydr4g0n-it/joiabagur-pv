/**
 * A field governed by a closed vocabulary (EP13 / C28).
 *
 * Offers the canonical terms and nothing else, for two separate reasons that do not coincide:
 *
 * **Reachability.** `materials` is matched downstream by `materials && ARRAY[…]` and `piece_type`
 * by `AND d.piece_type = :category`. A value outside the list is not wrong so much as
 * *unreachable*: no query can ever name it, because the search offers the same closed list. The
 * product keeps the term and no filter ever finds it again.
 *
 * **The measurement.** A term the vocabulary does not contain cannot have been produced by the
 * extractor, so recording it as an addition would count the vocabulary's coverage as the
 * extractor's error. Those are different defects with different remedies — one widens a
 * vocabulary in its own change, the other tightens a prompt — and merging them is exactly what
 * the direction of a correction exists to prevent.
 *
 * Which is why the escape hatch is **not** free text. When the source text names something the
 * vocabulary lacks, that is recorded as a *vocabulary gap*: a finding, deliberately kept out of
 * the correction rate, and the evidence that justifies widening the list in a later change.
 */
import { useState } from 'react';
import { Check, Plus, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { MaterialOption } from '@/lib/materials-vocabulary';

export interface VocabularyFieldProps {
  /** Field name, as the provenance documents key it. */
  field: string;
  /** Human label, for accessible names. */
  label: string;
  /** The canonical terms on offer. */
  options: readonly MaterialOption[];
  /** Whether the field holds several values or one. */
  isList: boolean;
  /** The values in force. */
  values: string[];
  /** Called with the new values in force. */
  onChange: (values: string[]) => void;
  /** Called when the reviewer records a term the vocabulary lacks. */
  onGap: (term: string) => void;
}

export function VocabularyField({
  field,
  label,
  options,
  isList,
  values,
  onChange,
  onGap,
}: VocabularyFieldProps) {
  const [open, setOpen] = useState(false);
  const [gapOpen, setGapOpen] = useState(false);
  const [gapTerm, setGapTerm] = useState('');

  const toggle = (value: string) => {
    if (!isList) {
      // A single-valued field: choosing the value already in force clears it, which is how a
      // removal is expressed without a separate control.
      onChange(values.includes(value) ? [] : [value]);
      setOpen(false);
      return;
    }

    onChange(
      values.includes(value) ? values.filter((v) => v !== value) : [...values, value],
    );
  };

  const recordGap = () => {
    const term = gapTerm.trim();
    if (!term) return;

    onGap(term);
    setGapTerm('');
    setGapOpen(false);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1">
        {values.length === 0 && (
          <span className="text-muted-foreground text-xs italic">
            ningún valor del vocabulario
          </span>
        )}
        {values.map((value) => (
          <Badge key={value} variant="secondary" className="gap-1">
            {options.find((option) => option.value === value)?.label ?? value}
            <button
              type="button"
              aria-label={`Quitar ${value} de ${label}`}
              onClick={() => toggle(value)}
            >
              <X className="size-3" />
            </button>
          </Badge>
        ))}

        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={label}
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <Plus className="size-3" />
          {isList ? 'Añadir' : 'Elegir'}
        </Button>
      </div>

      {open && (
        <div className="flex max-h-48 flex-wrap gap-1 overflow-y-auto rounded-md border p-2">
          {options.map((option) => (
            <Button
              key={option.value}
              type="button"
              variant={values.includes(option.value) ? 'primary' : 'outline'}
              size="sm"
              onClick={() => toggle(option.value)}
            >
              {values.includes(option.value) && <Check className="size-3" />}
              {option.label}
            </Button>
          ))}
        </div>
      )}

      {/* The escape hatch, which records a finding rather than a correction. */}
      {gapOpen ? (
        <div className="flex items-center gap-2">
          <Input
            aria-label={`Término que falta en el vocabulario de ${label}`}
            value={gapTerm}
            onChange={(event) => setGapTerm(event.target.value)}
            placeholder="el término que dice el texto"
            className="h-8"
          />
          <Button type="button" size="sm" onClick={recordGap}>
            Anotar
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => setGapOpen(false)}>
            Cancelar
          </Button>
        </div>
      ) : (
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground self-start text-xs underline"
          onClick={() => setGapOpen(true)}
          data-field={field}
        >
          El texto nombra algo que no está en la lista
        </button>
      )}
    </div>
  );
}

export default VocabularyField;
