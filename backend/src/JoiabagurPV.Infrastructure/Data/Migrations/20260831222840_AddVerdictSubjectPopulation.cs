using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace JoiabagurPV.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddVerdictSubjectPopulation : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<bool>(
                name: "SubjectWasMember",
                table: "FamilyReviewVerdicts",
                type: "boolean",
                nullable: false,
                defaultValue: false);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "SubjectWasMember",
                table: "FamilyReviewVerdicts");
        }
    }
}
