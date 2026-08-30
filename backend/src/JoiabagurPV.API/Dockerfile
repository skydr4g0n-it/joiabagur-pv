# DEPRECATED — imagen sólo-API, sin la SPA. No la construye ningún flujo.
#
# Su único consumidor era `backend/docker-compose.prod.yml`, también deprecado.
#
#   Producción:   `Dockerfile.bundled` (API + SPA), construida por
#                 `.github/workflows/deploy-aws-ec2.yml`
#   Demostración: `Dockerfile.demo` + `compose.demo.yaml` (C17)

# Build stage
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy solution and project files
COPY ["JoiabagurPV.sln", "."]
COPY ["JoiabagurPV.Domain/JoiabagurPV.Domain.csproj", "JoiabagurPV.Domain/"]
COPY ["JoiabagurPV.Infrastructure/JoiabagurPV.Infrastructure.csproj", "JoiabagurPV.Infrastructure/"]
COPY ["JoiabagurPV.Application/JoiabagurPV.Application.csproj", "JoiabagurPV.Application/"]
COPY ["JoiabagurPV.API/JoiabagurPV.API.csproj", "JoiabagurPV.API/"]

# Restore dependencies
RUN dotnet restore "JoiabagurPV.API/JoiabagurPV.API.csproj"

# Copy source code
COPY ["JoiabagurPV.Domain/", "JoiabagurPV.Domain/"]
COPY ["JoiabagurPV.Infrastructure/", "JoiabagurPV.Infrastructure/"]
COPY ["JoiabagurPV.Application/", "JoiabagurPV.Application/"]
COPY ["JoiabagurPV.API/", "JoiabagurPV.API/"]

# Build the application
WORKDIR "/src/JoiabagurPV.API"
RUN dotnet build "JoiabagurPV.API.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "JoiabagurPV.API.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

COPY --from=publish --chown=appuser:appuser /app/publish .

EXPOSE 8080
EXPOSE 8081

ENTRYPOINT ["dotnet", "JoiabagurPV.API.dll"]