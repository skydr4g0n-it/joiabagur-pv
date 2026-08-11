using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JoiabagurPV.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddProductSearchEventTracking : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "SearchEventId",
                table: "Sales",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "ProductSearchEvents",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    UserId = table.Column<Guid>(type: "uuid", nullable: false),
                    PointOfSaleId = table.Column<Guid>(type: "uuid", nullable: false),
                    SearchSessionId = table.Column<Guid>(type: "uuid", nullable: false),
                    SearchText = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: false),
                    FiltersJson = table.Column<string>(type: "jsonb", nullable: false),
                    ResultsJson = table.Column<string>(type: "jsonb", nullable: false),
                    ResultsCount = table.Column<int>(type: "integer", nullable: false),
                    SearchOrigin = table.Column<int>(type: "integer", nullable: false),
                    TraceId = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    RetrievalMs = table.Column<int>(type: "integer", nullable: true),
                    TotalMs = table.Column<int>(type: "integer", nullable: true),
                    SelectedProductId = table.Column<Guid>(type: "uuid", nullable: true),
                    SelectedFromRank = table.Column<int>(type: "integer", nullable: true),
                    SelectedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()"),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ProductSearchEvents", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ProductSearchEvents_PointOfSales_PointOfSaleId",
                        column: x => x.PointOfSaleId,
                        principalTable: "PointOfSales",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_ProductSearchEvents_Products_SelectedProductId",
                        column: x => x.SelectedProductId,
                        principalTable: "Products",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_ProductSearchEvents_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Sales_SearchEventId",
                table: "Sales",
                column: "SearchEventId");

            migrationBuilder.CreateIndex(
                name: "IX_ProductSearchEvents_CreatedAt",
                table: "ProductSearchEvents",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_ProductSearchEvents_PointOfSaleId_CreatedAt",
                table: "ProductSearchEvents",
                columns: new[] { "PointOfSaleId", "CreatedAt" });

            migrationBuilder.CreateIndex(
                name: "IX_ProductSearchEvents_SelectedProductId",
                table: "ProductSearchEvents",
                column: "SelectedProductId");

            migrationBuilder.CreateIndex(
                name: "IX_ProductSearchEvents_UserId",
                table: "ProductSearchEvents",
                column: "UserId");

            migrationBuilder.AddForeignKey(
                name: "FK_Sales_ProductSearchEvents_SearchEventId",
                table: "Sales",
                column: "SearchEventId",
                principalTable: "ProductSearchEvents",
                principalColumn: "Id",
                onDelete: ReferentialAction.SetNull);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Sales_ProductSearchEvents_SearchEventId",
                table: "Sales");

            migrationBuilder.DropTable(
                name: "ProductSearchEvents");

            migrationBuilder.DropIndex(
                name: "IX_Sales_SearchEventId",
                table: "Sales");

            migrationBuilder.DropColumn(
                name: "SearchEventId",
                table: "Sales");
        }
    }
}
