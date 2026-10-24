using JoiabagurPV.Application.DTOs.PointOfSales;
using JoiabagurPV.Application.Interfaces;
using JoiabagurPV.Domain.Entities;
using JoiabagurPV.Domain.Exceptions;
using JoiabagurPV.Domain.Interfaces.Repositories;

namespace JoiabagurPV.Application.Services;

public class PointOfSaleCommissionTierService : IPointOfSaleCommissionTierService
{
    private readonly IPointOfSaleCommissionTierRepository _tierRepository;
    private readonly IPointOfSaleRepository _pointOfSaleRepository;
    private readonly IUnitOfWork _unitOfWork;

    public PointOfSaleCommissionTierService(
        IPointOfSaleCommissionTierRepository tierRepository,
        IPointOfSaleRepository pointOfSaleRepository,
        IUnitOfWork unitOfWork)
    {
        _tierRepository = tierRepository;
        _pointOfSaleRepository = pointOfSaleRepository;
        _unitOfWork = unitOfWork;
    }

    public async Task<List<CommissionTierDto>> GetTiersAsync(Guid pointOfSaleId)
    {
        await EnsurePosExistsAsync(pointOfSaleId);
        var tiers = await _tierRepository.GetByPointOfSaleIdAsync(pointOfSaleId);
        return tiers.Select(MapToDto).ToList();
    }

    public async Task<List<CommissionTierDto>> ReplaceTiersAsync(Guid pointOfSaleId, ReplaceCommissionTiersRequest request)
    {
        await EnsurePosExistsAsync(pointOfSaleId);

        var entities = request.Tiers
            .OrderBy(t => t.MinAmountInclusive)
            .Select(t => new PointOfSaleCommissionTier
            {
                PointOfSaleId = pointOfSaleId,
                MinAmountInclusive = t.MinAmountInclusive,
                MaxAmountInclusive = t.MaxAmountInclusive,
                CommissionPercent = t.CommissionPercent
            })
            .ToList();

        await _tierRepository.ReplaceForPointOfSaleAsync(pointOfSaleId, entities);
        await _unitOfWork.SaveChangesAsync();

        return entities.Select(MapToDto).ToList();
    }

    private async Task EnsurePosExistsAsync(Guid pointOfSaleId)
    {
        var pos = await _pointOfSaleRepository.GetByIdAsync(pointOfSaleId);
        if (pos == null)
            throw new DomainException("Punto de venta no encontrado");
    }

    private static CommissionTierDto MapToDto(PointOfSaleCommissionTier tier) => new()
    {
        Id = tier.Id,
        MinAmountInclusive = tier.MinAmountInclusive,
        MaxAmountInclusive = tier.MaxAmountInclusive,
        CommissionPercent = tier.CommissionPercent
    };
}
