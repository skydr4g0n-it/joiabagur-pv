using FluentValidation;
using JoiabagurPV.Application.DTOs.GiftCards;
using JoiabagurPV.Domain.GiftCards;

namespace JoiabagurPV.Application.Validators;

public class IssueGiftCardRequestValidator : AbstractValidator<IssueGiftCardRequest>
{
    private static readonly decimal[] PresetAmounts = { 50m, 100m, 150m, 200m };

    public IssueGiftCardRequestValidator()
    {
        RuleFor(x => x.PointOfSaleId).NotEmpty();
        RuleFor(x => x.PaymentMethodId).NotEmpty();
        RuleFor(x => x.ExpiryDate)
            .Must(GiftCardEconomics.IsValidExpiryForIssuance)
            .WithMessage("La fecha de caducidad tiene que ser posterior a hoy (UTC).");
        RuleFor(x => x.HolderName)
            .MaximumLength(100)
            .When(x => !string.IsNullOrEmpty(x.HolderName));
        RuleFor(x => x.NominalAmount)
            .Must(IsAllowedNominal)
            .WithMessage("El importe tiene que ser 50, 100, 150 o 200 €, o un importe libre entre 0,01 y 99.999,99 con dos decimales como máximo.");
    }

    private static bool IsAllowedNominal(decimal amount)
    {
        if (amount != Math.Round(amount, 2))
            return false;

        if (PresetAmounts.Contains(amount))
            return true;

        return amount >= 0.01m && amount <= 99999.99m;
    }
}

public class ReassignGiftCardRequestValidator : AbstractValidator<ReassignGiftCardRequest>
{
    public ReassignGiftCardRequestValidator()
    {
        RuleFor(x => x.ToPointOfSaleId).NotEmpty();
    }
}

public class ExchangeGiftCardRequestValidator : AbstractValidator<ExchangeGiftCardRequest>
{
    public ExchangeGiftCardRequestValidator()
    {
        RuleFor(x => x.PointOfSaleId).NotEmpty();
        RuleFor(x => x.PaymentMethodId).NotEmpty();
        RuleFor(x => x.ReturnLines).NotEmpty();
        RuleFor(x => x.NewProducts).NotEmpty();
        RuleForEach(x => x.ReturnLines).ChildRules(line =>
        {
            line.RuleFor(l => l.SaleId).NotEmpty();
            line.RuleFor(l => l.Quantity).GreaterThan(0);
        });
        RuleForEach(x => x.NewProducts).ChildRules(line =>
        {
            line.RuleFor(l => l.ProductId).NotEmpty();
            line.RuleFor(l => l.Quantity).GreaterThan(0);
        });
    }
}
