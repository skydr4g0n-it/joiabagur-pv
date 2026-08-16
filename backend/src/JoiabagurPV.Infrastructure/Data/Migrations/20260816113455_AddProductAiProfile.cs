using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JoiabagurPV.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddProductAiProfile : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "ProductAiProfiles",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    ProductId = table.Column<Guid>(type: "uuid", nullable: false),
                    PieceType = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    MaterialsJson = table.Column<string>(type: "jsonb", nullable: false),
                    StoneType = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    SizeLabel = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true),
                    ColorTagsJson = table.Column<string>(type: "jsonb", nullable: false),
                    StyleTagsJson = table.Column<string>(type: "jsonb", nullable: false),
                    OccasionTagsJson = table.Column<string>(type: "jsonb", nullable: false),
                    AiConfidence = table.Column<decimal>(type: "numeric(4,3)", precision: 4, scale: 3, nullable: false),
                    FieldConfidenceJson = table.Column<string>(type: "jsonb", nullable: false),
                    FieldSourceJson = table.Column<string>(type: "jsonb", nullable: false),
                    ProposedProfileJson = table.Column<string>(type: "jsonb", nullable: false),
                    GeneratedByModel = table.Column<string>(type: "character varying(128)", maxLength: 128, nullable: true),
                    PromptVersion = table.Column<string>(type: "character varying(32)", maxLength: 32, nullable: true),
                    SourceHash = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: false),
                    ReviewStatus = table.Column<int>(type: "integer", nullable: false),
                    ReviewOrigin = table.Column<int>(type: "integer", nullable: false),
                    ReviewedByUserId = table.Column<Guid>(type: "uuid", nullable: true),
                    ReviewedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    ReviewDurationMs = table.Column<int>(type: "integer", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()"),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "NOW()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ProductAiProfiles", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ProductAiProfiles_Products_ProductId",
                        column: x => x.ProductId,
                        principalTable: "Products",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_ProductAiProfiles_Users_ReviewedByUserId",
                        column: x => x.ReviewedByUserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_ProductAiProfiles_ProductId",
                table: "ProductAiProfiles",
                column: "ProductId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_ProductAiProfiles_ReviewedByUserId",
                table: "ProductAiProfiles",
                column: "ReviewedByUserId");

            migrationBuilder.CreateIndex(
                name: "IX_ProductAiProfiles_ReviewStatus",
                table: "ProductAiProfiles",
                column: "ReviewStatus");

            migrationBuilder.CreateIndex(
                name: "IX_ProductAiProfiles_ReviewStatus_ReviewOrigin",
                table: "ProductAiProfiles",
                columns: new[] { "ReviewStatus", "ReviewOrigin" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ProductAiProfiles");
        }
    }
}
