using FluentValidation;
using JoiabagurPV.Application.DTOs.PointOfSales;

namespace JoiabagurPV.Application.Validators;

public class ReplaceCommissionTiersRequestValidator : AbstractValidator<ReplaceCommissionTiersRequest>
{
    public ReplaceCommissionTiersRequestValidator()
    {
        RuleForEach(x => x.Tiers).ChildRules(tier =>
        {
            tier.RuleFor(t => t.CommissionPercent)
                .InclusiveBetween(0, 100)
                .WithMessage("El porcentaje de comisión debe estar entre 0 y 100.");

            tier.RuleFor(t => t.MinAmountInclusive)
                .GreaterThanOrEqualTo(0)
                .WithMessage("El importe mínimo debe ser mayor o igual a 0.");

            tier.When(t => t.MaxAmountInclusive.HasValue, () =>
            {
                tier.RuleFor(t => t.MaxAmountInclusive!.Value)
                    .GreaterThanOrEqualTo(t => t.MinAmountInclusive)
                    .WithMessage("El importe máximo debe ser mayor o igual al mínimo.");
            });
        });

        RuleFor(x => x.Tiers)
            .Must(HaveValidTierStructure)
            .WithMessage("Los tramos deben empezar en 0, ser contiguos y tener un solo tramo sin máximo al final.");
    }

    private static bool HaveValidTierStructure(List<CommissionTierInputDto> tiers)
    {
        if (tiers.Count == 0)
            return true;

        var ordered = tiers.OrderBy(t => t.MinAmountInclusive).ToList();

        if (ordered[0].MinAmountInclusive != 0)
            return false;

        var openEndedCount = ordered.Count(t => t.MaxAmountInclusive == null);
        if (openEndedCount > 1)
            return false;

        if (openEndedCount == 1 && ordered[^1].MaxAmountInclusive != null)
            return false;

        for (var i = 0; i < ordered.Count; i++)
        {
            var tier = ordered[i];
            if (tier.MaxAmountInclusive.HasValue && tier.MaxAmountInclusive < tier.MinAmountInclusive)
                return false;

            if (i < ordered.Count - 1)
            {
                var next = ordered[i + 1];
                if (!tier.MaxAmountInclusive.HasValue)
                    return false;

                if (next.MinAmountInclusive != tier.MaxAmountInclusive.Value + 1m)
                    return false;
            }
        }

        return true;
    }
}
