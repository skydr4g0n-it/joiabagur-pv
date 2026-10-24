using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JoiabagurPV.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddPointOfSaleCommissionTiers : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "PointOfSaleCommissionTiers",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    PointOfSaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    MinAmountInclusive = table.Column<decimal>(type: "numeric(18,2)", nullable: false),
                    MaxAmountInclusive = table.Column<decimal>(type: "numeric(18,2)", nullable: true),
                    CommissionPercent = table.Column<decimal>(type: "numeric(5,2)", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()"),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_PointOfSaleCommissionTiers", x => x.Id);
                    table.ForeignKey(
                        name: "FK_PointOfSaleCommissionTiers_PointOfSales_PointOfSaleId",
                        column: x => x.PointOfSaleId,
                        principalTable: "PointOfSales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_PointOfSaleCommissionTiers_PointOfSaleId",
                table: "PointOfSaleCommissionTiers",
                column: "PointOfSaleId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "PointOfSaleCommissionTiers");
        }
    }
}
