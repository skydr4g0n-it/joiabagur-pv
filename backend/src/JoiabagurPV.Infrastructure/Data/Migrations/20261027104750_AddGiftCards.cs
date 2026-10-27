using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JoiabagurPV.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddGiftCards : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "SystemProductKind",
                table: "Products",
                type: "integer",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "GiftCards",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    Code = table.Column<string>(type: "character varying(16)", maxLength: 16, nullable: false),
                    PointOfSaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    HolderName = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: true),
                    NominalAmount = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    SpendableBalance = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    ExpiryDate = table.Column<DateOnly>(type: "date", nullable: false),
                    IssuanceSaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    IssuedByUserId = table.Column<Guid>(type: "uuid", nullable: false),
                    IssuanceIdempotencyKey = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()"),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_GiftCards", x => x.Id);
                    table.ForeignKey(
                        name: "FK_GiftCards_PointOfSales_PointOfSaleId",
                        column: x => x.PointOfSaleId,
                        principalTable: "PointOfSales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_GiftCards_Sales_IssuanceSaleId",
                        column: x => x.IssuanceSaleId,
                        principalTable: "Sales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_GiftCards_Users_IssuedByUserId",
                        column: x => x.IssuedByUserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "GiftCardCoverageEntries",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    GiftCardId = table.Column<Guid>(type: "uuid", nullable: false),
                    SaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    EntryType = table.Column<int>(type: "integer", nullable: false),
                    Amount = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    EntryDate = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()"),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_GiftCardCoverageEntries", x => x.Id);
                    table.ForeignKey(
                        name: "FK_GiftCardCoverageEntries_GiftCards_GiftCardId",
                        column: x => x.GiftCardId,
                        principalTable: "GiftCards",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_GiftCardCoverageEntries_Sales_SaleId",
                        column: x => x.SaleId,
                        principalTable: "Sales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "GiftCardReassignments",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    GiftCardId = table.Column<Guid>(type: "uuid", nullable: false),
                    FromPointOfSaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    ToPointOfSaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    UserId = table.Column<Guid>(type: "uuid", nullable: false),
                    OccurredAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()"),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_GiftCardReassignments", x => x.Id);
                    table.ForeignKey(
                        name: "FK_GiftCardReassignments_GiftCards_GiftCardId",
                        column: x => x.GiftCardId,
                        principalTable: "GiftCards",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_GiftCardReassignments_PointOfSales_FromPointOfSaleId",
                        column: x => x.FromPointOfSaleId,
                        principalTable: "PointOfSales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_GiftCardReassignments_PointOfSales_ToPointOfSaleId",
                        column: x => x.ToPointOfSaleId,
                        principalTable: "PointOfSales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_GiftCardReassignments_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_GiftCardCoverageEntries_GiftCardId_EntryDate",
                table: "GiftCardCoverageEntries",
                columns: new[] { "GiftCardId", "EntryDate" });

            migrationBuilder.CreateIndex(
                name: "IX_GiftCardCoverageEntries_SaleId",
                table: "GiftCardCoverageEntries",
                column: "SaleId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCardReassignments_FromPointOfSaleId",
                table: "GiftCardReassignments",
                column: "FromPointOfSaleId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCardReassignments_GiftCardId",
                table: "GiftCardReassignments",
                column: "GiftCardId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCardReassignments_ToPointOfSaleId",
                table: "GiftCardReassignments",
                column: "ToPointOfSaleId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCardReassignments_UserId",
                table: "GiftCardReassignments",
                column: "UserId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCards_Code",
                table: "GiftCards",
                column: "Code",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_GiftCards_IssuanceIdempotencyKey",
                table: "GiftCards",
                column: "IssuanceIdempotencyKey",
                unique: true,
                filter: "\"IssuanceIdempotencyKey\" IS NOT NULL");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCards_IssuanceSaleId",
                table: "GiftCards",
                column: "IssuanceSaleId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCards_IssuedByUserId",
                table: "GiftCards",
                column: "IssuedByUserId");

            migrationBuilder.CreateIndex(
                name: "IX_GiftCards_PointOfSaleId",
                table: "GiftCards",
                column: "PointOfSaleId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "GiftCardCoverageEntries");

            migrationBuilder.DropTable(
                name: "GiftCardReassignments");

            migrationBuilder.DropTable(
                name: "GiftCards");

            migrationBuilder.DropColumn(
                name: "SystemProductKind",
                table: "Products");
        }
    }
}
