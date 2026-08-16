using FluentValidation;
using JoiabagurPV.Application.DTOs.Products;
using JoiabagurPV.Application.Exceptions;
using JoiabagurPV.Application.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace JoiabagurPV.API.Controllers;

/// <summary>
/// Controller for product family management — variants of one piece grouped as an editable entity.
/// </summary>
/// <remarks>
/// Writing is restricted to administrators, in line with the rest of catalogue administration.
/// Reading is open to any authenticated user and is <strong>not</strong> filtered by assigned points
/// of sale: family membership is a fact about the catalogue, not about stock, and applying inventory
/// visibility here would make the sibling list depend on where a piece happens to be held.
/// </remarks>
[ApiController]
[Route("api/product-families")]
[Authorize]
public class ProductFamiliesController : ControllerBase
{
    private readonly IProductFamilyService _familyService;
    private readonly IValidator<CreateProductFamilyRequest> _createValidator;
    private readonly IValidator<UpdateProductFamilyRequest> _updateValidator;
    private readonly IValidator<ReplaceFamilyMembersRequest> _membersValidator;

    public ProductFamiliesController(
        IProductFamilyService familyService,
        IValidator<CreateProductFamilyRequest> createValidator,
        IValidator<UpdateProductFamilyRequest> updateValidator,
        IValidator<ReplaceFamilyMembersRequest> membersValidator)
    {
        _familyService = familyService;
        _createValidator = createValidator;
        _updateValidator = updateValidator;
        _membersValidator = membersValidator;
    }

    /// <summary>
    /// Gets a family with its members, ordered by their position within it.
    /// </summary>
    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(ProductFamilyDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetById(Guid id)
    {
        var family = await _familyService.GetByIdAsync(id);
        if (family is null)
            return NotFound();

        return Ok(family);
    }

    /// <summary>
    /// Creates a family, optionally with its members already declared.
    /// </summary>
    [HttpPost]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ProductFamilyDto), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Create([FromBody] CreateProductFamilyRequest request)
    {
        // Validated explicitly: this project registers validators but wires no automatic pipeline,
        // so an uninvoked validator is worse than none — it looks like validation.
        var validation = await _createValidator.ValidateAsync(request);
        if (!validation.IsValid)
            return BadRequest(new { errors = validation.Errors.Select(error => error.ErrorMessage) });

        try
        {
            var family = await _familyService.CreateAsync(request);
            return CreatedAtAction(nameof(GetById), new { id = family.Id }, family);
        }
        catch (ProductFamilyConflictException exception)
        {
            return Conflict(new { error = exception.Message, conflicts = exception.Conflicts });
        }
    }

    /// <summary>
    /// Corrects a family's name and description. Its members are left untouched.
    /// </summary>
    [HttpPut("{id:guid}")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ProductFamilyDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Update(Guid id, [FromBody] UpdateProductFamilyRequest request)
    {
        var validation = await _updateValidator.ValidateAsync(request);
        if (!validation.IsValid)
            return BadRequest(new { errors = validation.Errors.Select(error => error.ErrorMessage) });

        // A missing family surfaces as KeyNotFoundException, which the exception middleware already
        // translates to 404.
        var family = await _familyService.UpdateAsync(id, request);
        return Ok(family);
    }

    /// <summary>
    /// Declares the complete membership of a family.
    /// </summary>
    /// <remarks>
    /// Whatever is absent from the declaration stops being a member, and each member's position
    /// comes from its place in the list. An empty declaration dissolves the family without deleting
    /// it. Declaring the list the family already has writes nothing.
    /// </remarks>
    [HttpPut("{id:guid}/members")]
    [Authorize(Roles = "Administrator")]
    [ProducesResponseType(typeof(ProductFamilyDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    [ProducesResponseType(StatusCodes.Status403Forbidden)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> ReplaceMembers(
        Guid id,
        [FromBody] ReplaceFamilyMembersRequest request)
    {
        var validation = await _membersValidator.ValidateAsync(request);
        if (!validation.IsValid)
            return BadRequest(new { errors = validation.Errors.Select(error => error.ErrorMessage) });

        try
        {
            var family = await _familyService.ReplaceMembersAsync(id, request);
            return Ok(family);
        }
        catch (ProductFamilyConflictException exception)
        {
            // Translated by type, not by sniffing the message: the conflicting products travel on
            // the exception, so the response can name them and the family that holds each one.
            return Conflict(new { error = exception.Message, conflicts = exception.Conflicts });
        }
    }
}
