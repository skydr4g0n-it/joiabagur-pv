-- Backfill de `SubjectWasMember` para los 58 veredictos de la revisión del 2026-08-31.
--
-- La columna se añadió después de que registraras la revisión, así que las 58 filas quedaron
-- en `false` por defecto. Dieciocho de ellas eran miembros marcados, no candidatos, y sin
-- corregirlo la métrica de corrección del agrupador saldría como 0 de 18 en vez de 17 de 18.
--
-- **No lo ejecuto yo.** Escribe sobre tus datos de revisión, y la reconstrucción es una
-- inferencia mía, no un dato guardado. Revísala antes de aplicarla.
--
-- Cómo se reconstruye, y por qué esto es exacto:
--
--   * Los 17 miembros confirmados siguen siendo miembros de su familia -> derivables.
--   * El miembro rechazado (SKU91) se sacó de la familia -> hay que nombrarlo.
--   * Los 6 candidatos confirmados AHORA son miembros, así que derivarlos por pertenencia
--     actual los marcaría como miembros y son candidatos -> hay que excluirlos.
--   * Los 34 candidatos rechazados nunca fueron miembros -> el `false` por defecto ya es correcto.
--
-- Los siete SKU nombrados son exactamente los que aplicaste, verificados uno a uno.
--
-- Ejecutar con:
--   docker exec -i jpv-pv-postgres psql -U postgres -d joiabagur_pv < backfill-subject-population.sql

BEGIN;

UPDATE public."FamilyReviewVerdicts" v
SET "SubjectWasMember" = TRUE
FROM public."Products" p
WHERE p."Id" = v."ProductId"
  AND (
    -- Miembros que siguen siéndolo: los 17 confirmados.
    (EXISTS (SELECT 1 FROM public."ProductFamilyMembers" m
             WHERE m."ProductId" = v."ProductId"
               AND m."ProductFamilyId" = v."ProductFamilyId")
     AND p."SKU" NOT IN ('SKU25','SKU420','SKU90','SKU133','SKU17','SKU119'))
    -- El miembro rechazado, que ya no es miembro porque se aplicó la decisión.
    OR p."SKU" = 'SKU91'
  );

-- Comprobación: deben quedar 18 en TRUE y 40 en FALSE.
SELECT "SubjectWasMember", count(*) AS filas
FROM public."FamilyReviewVerdicts"
GROUP BY 1
ORDER BY 1;

-- Y la métrica debe leer 17 de 18 miembros confirmados, 6 de 40 candidatos aceptados.
SELECT
  count(*) FILTER (WHERE "SubjectWasMember")                          AS miembros_juzgados,
  count(*) FILTER (WHERE "SubjectWasMember" AND "Outcome" = 1)        AS miembros_confirmados,
  count(*) FILTER (WHERE NOT "SubjectWasMember")                      AS candidatos_juzgados,
  count(*) FILTER (WHERE NOT "SubjectWasMember" AND "Outcome" = 1)    AS candidatos_aceptados
FROM public."FamilyReviewVerdicts";

COMMIT;
