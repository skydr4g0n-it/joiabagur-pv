# =============================================================================
# pr-context.ps1
#
# FASE A del generador de Pull Requests: recopilacion de contexto Git y troceo
# (chunking) DETERMINISTA del diff. No interviene ningun modelo de lenguaje en
# esta fase -> cero alucinacion en la recoleccion.
#
# Produce, en <repo>/.pr/<rama>/ :
#   manifest.json       Metadatos: ramas, commits, stats, dominios y chunks.
#   chunks/NN-<dom>.diff Un diff por grupo de dominio (troceado si es grande).
#   summary.md          Resumen legible por humanos.
#
# Cada rama tiene su subcarpeta (slug de la rama). Las subcarpetas de ramas que
# ya no existen se podan automaticamente en cada ejecucion (autolimpieza).
#
# La rama base NUNCA se asume: hay que pasarla con -BaseBranch. Si falta, el
# script se detiene, sugiere la que detectaria (origin/HEAD) y lista candidatas,
# para que quien lo invoca pregunte al usuario. -AutoBase acepta la sugerencia de
# forma explicita (uso desatendido).
#
# Por defecto refresca la rama base con `git fetch origin <base>` para no
# comparar contra una copia local desactualizada (-NoFetch lo desactiva).
#
# La skill `generate-pr` consume manifest.json y analiza los chunks de uno en
# uno (contexto incremental). Ver SKILL.md.
#
# Este script esta replicado en .agent/, .claude/, .codex/, .cursor/ y
# .opencode/skills/generate-pr/scripts/. Editar una copia y replicarla al resto.
#
# Uso:
#   ./pr-context.ps1 -BaseBranch <rama> [-OutDir .pr] [-NoFetch]
#   ./pr-context.ps1 -AutoBase              # acepta la base detectada, sin preguntar
# =============================================================================

[CmdletBinding()]
param(
    [string]$BaseBranch = "",
    [string]$OutDir = ".pr",
    [int]$MaxChunkLines = 0,
    [int]$MaxFileLines = 0,
    [switch]$NoFetch,
    [switch]$AutoBase
)

$ErrorActionPreference = "Stop"

# --- Utilidades ---------------------------------------------------------------

function Invoke-Git {
    # Ejecuta git y devuelve stdout como string; lanza si el codigo de salida != 0.
    param([string[]]$GitArgs, [switch]$AllowFail)
    $out = & git @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0 -and -not $AllowFail) {
        throw "git $($GitArgs -join ' ') fallo (codigo $LASTEXITCODE): $out"
    }
    return ($out -join "`n")
}

function Convert-GlobToRegex {
    # Convierte un glob ('*' segmento, '**' cualquier ruta, '**/' prefijo opcional)
    # en una expresion regular anclada.
    param([string]$Glob)
    $p = [Regex]::Escape(($Glob -replace '\\', '/'))
    $p = $p -replace '\\\*\\\*/', '(?:.*/)?'
    $p = $p -replace '\\\*\\\*', '.*'
    $p = $p -replace '\\\*', '[^/]*'
    $p = $p -replace '\\\?', '.'
    return "^$p$"
}

function Write-TextLf {
    param([string]$Path, [string]$Content)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $normalized = ($Content -replace "`r`n", "`n")
    [System.IO.File]::WriteAllText($Path, $normalized, (New-Object System.Text.UTF8Encoding($false)))
}

# --- Localizacion del repo y la configuracion ---------------------------------

$repoRoot = (Invoke-Git @("rev-parse", "--show-toplevel")).Trim()
if (-not $repoRoot) { throw "No estas dentro de un repositorio Git." }
Set-Location $repoRoot

$configPath = Join-Path $PSScriptRoot "../config/domains.json"
if (-not (Test-Path $configPath)) { throw "No se encuentra la configuracion de dominios: $configPath" }
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json

if ($MaxChunkLines -le 0) { $MaxChunkLines = [int]$config.chunking.maxChunkLines }
if ($MaxFileLines  -le 0) { $MaxFileLines  = [int]$config.chunking.maxFileLines }

# --- Deteccion del repo (via repoMarkers de domains.json) ---------------------

$repoKey = "_default"
foreach ($prop in $config.repoMarkers.PSObject.Properties) {
    foreach ($marker in $prop.Value) {
        if (Test-Path (Join-Path $repoRoot $marker)) { $repoKey = $prop.Name; break }
    }
    if ($repoKey -ne "_default") { break }
}

# --- Ramas y merge-base -------------------------------------------------------

$currentBranch = (Invoke-Git @("rev-parse", "--abbrev-ref", "HEAD")).Trim()

# Base SUGERIDA. Ojo: es solo una sugerencia, no se aplica sola (ver bloque
# siguiente). La rama base la decide siempre una persona.
function Get-SuggestedBase {
    $head = (Invoke-Git @("rev-parse", "--abbrev-ref", "origin/HEAD") -AllowFail).Trim()
    if ($head -and $head -notmatch "fatal") { return ($head -replace "^origin/", "") }
    if ((Invoke-Git @("rev-parse", "--verify", "origin/main")   -AllowFail) -notmatch "fatal") { return "main" }
    if ((Invoke-Git @("rev-parse", "--verify", "origin/master") -AllowFail) -notmatch "fatal") { return "master" }
    return ""
}

# REGLA: la rama base NUNCA se da por sentada.
# Sin -BaseBranch explicito (o -AutoBase como consentimiento explicito a la
# deteccion), el script se detiene sin generar nada: quien lo invoca debe
# preguntar antes al usuario contra que rama quiere abrir la PR.
if (-not $BaseBranch) {
    $suggested = Get-SuggestedBase
    if ($AutoBase) {
        if (-not $suggested) { throw "No se pudo detectar ninguna rama base y no se indico -BaseBranch." }
        $BaseBranch = $suggested
        Write-Host "pr-context :: -AutoBase: se usa la base detectada '$BaseBranch'." -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "pr-context :: falta la rama base. No se asume ninguna." -ForegroundColor Yellow
        Write-Host "  Rama actual (origen de la PR): $currentBranch" -ForegroundColor DarkGray
        if ($suggested) {
            Write-Host "  Sugerencia (origin/HEAD):      $suggested" -ForegroundColor Cyan
        } else {
            Write-Host "  Sin sugerencia: 'origin/HEAD' no esta definido en este clon." -ForegroundColor DarkGray
        }
        $cands = @()
        $remoteRaw = Invoke-Git @("branch", "-r", "--format=%(refname:short)") -AllowFail
        if ($LASTEXITCODE -eq 0) {
            # Solo refs con '<remoto>/<rama>'. Descarta la abreviatura del
            # simbolico refs/remotes/origin/HEAD, que git muestra como 'origin'.
            $cands = @($remoteRaw -split "`n" |
                ForEach-Object { $_.Trim() } |
                Where-Object { $_ -match '/' } |
                ForEach-Object { ($_ -split '/', 2)[1] } |
                Where-Object { $_ -and $_ -ne 'HEAD' -and $_ -ne $currentBranch } |
                Select-Object -Unique)
        }
        if ($cands.Count -gt 0) {
            Write-Host "  Candidatas:                    $($cands -join ', ')" -ForegroundColor Cyan
        }
        Write-Host ""
        Write-Host "  Reejecuta indicando la base:   -BaseBranch <rama>" -ForegroundColor Green
        Write-Host "  (o -AutoBase para aceptar explicitamente la sugerencia)" -ForegroundColor DarkGray
        Write-Host ""
        exit 2
    }
}

# Refresca la rama base desde el remoto para no comparar contra una copia local
# obsoleta de origin/<base>. Fail-soft: si no hay red/remoto, avisa y continua.
if (-not $NoFetch) {
    Invoke-Git @("fetch", "origin", $BaseBranch, "--quiet") -AllowFail | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pr-context :: aviso: 'git fetch origin $BaseBranch' fallo; se usa la copia local de origin/$BaseBranch." -ForegroundColor Yellow
    }
}

# Resuelve la referencia base: prefiere origin/<base>, cae a <base> local.
$baseRef = "origin/$BaseBranch"
if ((Invoke-Git @("rev-parse", "--verify", $baseRef) -AllowFail) -match "fatal") {
    $baseRef = $BaseBranch
}

$mergeBase = ""
$mergeBaseRaw = Invoke-Git @("merge-base", $baseRef, "HEAD") -AllowFail
if ($LASTEXITCODE -eq 0) { $mergeBase = $mergeBaseRaw.Trim() }

# --- Preparar carpeta de salida ----------------------------------------------

# Cada rama tiene su subcarpeta: .pr/<slug>/. El slug sanea separadores y
# caracteres no seguros de la rama a guiones.
$branchSlug = ($currentBranch -replace '[^\w.-]+', '-').Trim('-')
if (-not $branchSlug) { $branchSlug = "HEAD" }

$prRoot    = Join-Path $repoRoot $OutDir          # .pr/
$outRoot   = Join-Path $prRoot $branchSlug        # .pr/<slug>/
$outRel    = "$OutDir/$branchSlug"                # ruta relativa para manifest
$chunksDir = Join-Path $outRoot "chunks"
if (Test-Path $outRoot) { Remove-Item -Recurse -Force $outRoot }
New-Item -ItemType Directory -Force -Path $chunksDir | Out-Null

# Autolimpieza: poda subcarpetas de .pr/ cuyas ramas ya no existen, y restos del
# formato antiguo (ficheros sueltos o carpetas sin manifest en la raiz de .pr/).
function Remove-StalePrFolders {
    if (-not (Test-Path $prRoot)) { return }
    foreach ($entry in (Get-ChildItem -LiteralPath $prRoot -Force)) {
        if ($entry.Name -eq $branchSlug) { continue }   # nunca la del run actual
        if ($entry.PSIsContainer) {
            $em = Join-Path $entry.FullName "manifest.json"
            if (Test-Path $em) {
                $branch = $null
                try { $branch = (Get-Content -Raw -LiteralPath $em | ConvertFrom-Json).currentBranch } catch { }
                if (-not $branch) { continue }          # manifest ilegible: conservar
                & git rev-parse --verify --quiet "refs/heads/$branch" *> $null
                if ($LASTEXITCODE -ne 0) {
                    Remove-Item -Recurse -Force $entry.FullName
                    Write-Host "  autolimpieza: .pr/$($entry.Name) eliminada (rama '$branch' ya no existe)" -ForegroundColor DarkGray
                }
            } else {
                Remove-Item -Recurse -Force $entry.FullName   # carpeta sin manifest (formato antiguo)
            }
        } else {
            Remove-Item -Force $entry.FullName                 # fichero suelto (formato antiguo)
        }
    }
}

# --- Caso: no hay base valida o no hay cambios --------------------------------

function Write-EmptyManifest {
    param([string]$Reason)
    $manifest = [ordered]@{
        generatedAt   = (Get-Date).ToString("o")
        repo          = $repoKey
        baseBranch    = $BaseBranch
        currentBranch = $currentBranch
        mergeBase     = $mergeBase
        outDir        = $outRel
        empty         = $true
        reason        = $Reason
        stats         = @{ filesChanged = 0; insertions = 0; deletions = 0 }
        commits       = @()
        domains       = @()
        siblingRepos  = @()
    }
    Write-TextLf -Path (Join-Path $outRoot "manifest.json") -Content ($manifest | ConvertTo-Json -Depth 8)
    Write-TextLf -Path (Join-Path $outRoot "summary.md") -Content "# Contexto PR`n`n$Reason`n"
    Remove-StalePrFolders
    Write-Host "pr-context :: $Reason" -ForegroundColor Yellow
}

if (-not $mergeBase) {
    Write-EmptyManifest "No se pudo determinar un ancestro común con '$BaseBranch'. Verifica la rama base o ejecuta 'git fetch'."
    exit 0
}

$nameStatus = (Invoke-Git @("diff", "--name-status", "$mergeBase", "HEAD")).Trim()
if (-not $nameStatus) {
    Write-EmptyManifest "No hay diferencias entre '$currentBranch' y '$BaseBranch'. Confirma que los cambios estén commiteados."
    exit 0
}

# --- Parsear archivos cambiados (name-status + numstat) -----------------------

$numstat = (Invoke-Git @("diff", "--numstat", "$mergeBase", "HEAD")).Trim()
$numMap = @{}
foreach ($line in ($numstat -split "`n")) {
    $parts = $line -split "`t"
    if ($parts.Count -ge 3) {
        $numMap[$parts[2]] = @{ added = $parts[0]; deleted = $parts[1] }
    }
}

$files = @()
foreach ($line in ($nameStatus -split "`n")) {
    if (-not $line.Trim()) { continue }
    $parts = $line -split "`t"
    $status = $parts[0].Substring(0, 1)
    # Renombrados (R100) usan la ruta destino como path de analisis.
    $path = if ($status -eq "R" -and $parts.Count -ge 3) { $parts[2] } else { $parts[1] }
    $n = $numMap[$path]
    $files += [pscustomobject]@{
        path    = $path
        status  = $status
        added   = if ($n) { $n.added } else { "0" }
        deleted = if ($n) { $n.deleted } else { "0" }
    }
}

# --- Clasificar cada archivo en un dominio ------------------------------------

# Precompila los globs de los dominios aplicables a este repo (o 'any').
$activeDomains = @()
foreach ($d in $config.domains) {
    if ($d.repo -eq "any" -or $d.repo -eq $repoKey) {
        $regexes = @($d.globs | ForEach-Object { Convert-GlobToRegex $_ })
        $activeDomains += [pscustomobject]@{ name = $d.name; priority = $d.priority; regexes = $regexes }
    }
}

function Get-DomainForFile {
    param([string]$Path)
    foreach ($d in $activeDomains) {
        foreach ($rx in $d.regexes) {
            if ($Path -match $rx) { return $d.name }
        }
    }
    return $config.fallbackDomain
}

$grouped = [ordered]@{}
foreach ($f in $files) {
    $dom = Get-DomainForFile $f.path
    if (-not $grouped.Contains($dom)) { $grouped[$dom] = @() }
    $grouped[$dom] += $f
}

# --- Generar los chunks de diff por dominio -----------------------------------

function Get-FileDiff {
    param([string]$FilePath)
    $raw = Invoke-Git @("diff", "$mergeBase", "HEAD", "--", $FilePath) -AllowFail
    $lineCount = ($raw -split "`n").Count
    if ($script:summarize -and $lineCount -gt $MaxFileLines) {
        # Archivo enorme: conservar solo cabecera y hunk headers (@@ ... @@).
        $kept = @()
        foreach ($l in ($raw -split "`n")) {
            if ($l -match '^(diff --git|index |--- |\+\+\+ |@@ |rename |new file|deleted file|similarity)') {
                $kept += $l
            }
        }
        $kept += "# [pr-context] Diff resumido: $lineCount lineas > umbral $MaxFileLines. Solo se muestran las cabeceras de hunk."
        return @{ text = ($kept -join "`n"); truncated = $true; lines = $lineCount }
    }
    return @{ text = $raw; truncated = $false; lines = $lineCount }
}

$script:summarize = [bool]$config.chunking.summarizeOversizedFiles
$domainEntries = @()
$chunkIndex = 0
$totalAdded = 0
$totalDeleted = 0

foreach ($dom in $grouped.Keys) {
    $domFiles = $grouped[$dom]
    $domAdded   = ($domFiles | ForEach-Object { [int]($_.added   -replace '-', '0') } | Measure-Object -Sum).Sum
    $domDeleted = ($domFiles | ForEach-Object { [int]($_.deleted -replace '-', '0') } | Measure-Object -Sum).Sum
    $totalAdded += $domAdded
    $totalDeleted += $domDeleted

    # Construye los diffs por archivo y los agrupa en chunks <= MaxChunkLines.
    $fileDiffs = @()
    foreach ($f in $domFiles) {
        $fd = Get-FileDiff $f.path
        $fileDiffs += [pscustomobject]@{ path = $f.path; text = $fd.text; lines = $fd.lines; truncated = $fd.truncated }
    }

    # Agrupa los diffs de archivo en chunks de <= MaxChunkLines lineas.
    # Un archivo nunca se parte: si por si solo supera el umbral, ocupa su chunk.
    $chunkGroups = @()
    $cur = $null
    foreach ($fd in $fileDiffs) {
        if ($null -ne $cur -and ($cur.lines + $fd.lines) -gt $MaxChunkLines) {
            $chunkGroups += $cur
            $cur = $null
        }
        if ($null -eq $cur) {
            $cur = [pscustomobject]@{ texts = @(); files = @(); lines = 0; truncated = $false }
        }
        $cur.texts += $fd.text
        $cur.files += $fd.path
        $cur.lines += $fd.lines
        if ($fd.truncated) { $cur.truncated = $true }
    }
    if ($null -ne $cur) { $chunkGroups += $cur }

    $chunks = @()
    foreach ($g in $chunkGroups) {
        $chunkIndex++
        $idx = "{0:D2}" -f $chunkIndex
        $chunkPath = Join-Path $chunksDir "$idx-$dom.diff"
        Write-TextLf -Path $chunkPath -Content (($g.texts -join "`n") + "`n")
        $chunks += [pscustomobject]@{
            path      = "$outRel/chunks/$idx-$dom.diff"
            files     = $g.files
            lines     = $g.lines
            truncated = $g.truncated
        }
    }

    $domainEntries += [pscustomobject]@{
        name       = $dom
        files      = @($domFiles | ForEach-Object { @{ path = $_.path; status = $_.status; added = $_.added; deleted = $_.deleted } })
        insertions = $domAdded
        deletions  = $domDeleted
        chunks     = $chunks
    }
}

# --- Commits ------------------------------------------------------------------

$logRaw = (Invoke-Git @("log", "$mergeBase..HEAD", "--pretty=format:%H%x09%s")).Trim()
$commits = @()
foreach ($line in ($logRaw -split "`n")) {
    if (-not $line.Trim()) { continue }
    $p = $line -split "`t", 2
    $commits += @{ hash = $p[0]; subject = if ($p.Count -gt 1) { $p[1] } else { "" } }
}

# --- Cambios sin commitear (aviso) --------------------------------------------

$dirty = (Invoke-Git @("status", "--porcelain")).Trim()
$hasUncommitted = [bool]$dirty

# --- Awareness multi-repo: buscar la misma rama en repos hermanos -------------
#
# joiabagur-pv es un monorepo (backend + frontend + ai-service + terraform), asi
# que 'siblingRepos' en domains.json esta vacio y este bloque no hace nada. Se
# conserva por si en el futuro se extrae algun componente a su propio repo:
# basta con anadir el nombre de la carpeta hermana a esa lista.

$siblingRepos = @()
$parent = Split-Path -Parent $repoRoot
$repoLeaf = Split-Path -Leaf $repoRoot
foreach ($sibName in @($config.siblingRepos)) {
    if (-not $sibName -or $sibName -eq $repoLeaf) { continue }
    $sibPath = Join-Path $parent $sibName
    if (Test-Path (Join-Path $sibPath ".git")) {
        $match = & git -C $sibPath rev-parse --verify $currentBranch 2>$null
        $siblingRepos += @{
            repo        = $sibName
            path        = "../$sibName"
            branchMatch = ($LASTEXITCODE -eq 0 -and [bool]$match)
        }
    }
}

# --- Escribir manifest.json ---------------------------------------------------

$manifest = [ordered]@{
    generatedAt    = (Get-Date).ToString("o")
    repo           = $repoKey
    baseBranch     = $BaseBranch
    baseRef        = $baseRef
    currentBranch  = $currentBranch
    mergeBase      = $mergeBase
    outDir         = $outRel
    empty          = $false
    hasUncommitted = $hasUncommitted
    chunking       = @{ maxChunkLines = $MaxChunkLines; maxFileLines = $MaxFileLines }
    stats          = @{
        filesChanged = $files.Count
        insertions   = $totalAdded
        deletions    = $totalDeleted
        chunks       = $chunkIndex
    }
    commits        = $commits
    domains        = $domainEntries
    siblingRepos   = $siblingRepos
}
Write-TextLf -Path (Join-Path $outRoot "manifest.json") -Content ($manifest | ConvertTo-Json -Depth 12)

# --- Escribir summary.md (legible) --------------------------------------------

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine("# Contexto PR — $repoKey")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("- Rama base: ``$BaseBranch`` ($baseRef)")
[void]$sb.AppendLine("- Rama actual: ``$currentBranch``")
[void]$sb.AppendLine("- Merge-base: ``$mergeBase``")
[void]$sb.AppendLine("- Archivos cambiados: $($files.Count)  (+$totalAdded / -$totalDeleted)")
[void]$sb.AppendLine("- Chunks generados: $chunkIndex")
if ($hasUncommitted) {
    [void]$sb.AppendLine("- AVISO: hay cambios sin commitear; NO entran en el diff analizado.")
}
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Commits ($($commits.Count))")
foreach ($c in $commits) { [void]$sb.AppendLine("- $($c.subject)") }
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Dominios y chunks")
foreach ($d in $domainEntries) {
    [void]$sb.AppendLine("- **$($d.name)** — $($d.files.Count) archivo(s), +$($d.insertions)/-$($d.deletions)")
    foreach ($ch in $d.chunks) {
        $t = if ($ch.truncated) { " [resumido]" } else { "" }
        [void]$sb.AppendLine("  - ``$($ch.path)`` ($($ch.lines) lineas)$t")
    }
}
if ($siblingRepos.Count -gt 0) {
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Repos hermanos")
    foreach ($s in $siblingRepos) {
        $m = if ($s.branchMatch) { "rama '$currentBranch' PRESENTE — posible PR coordinada" } else { "sin la rama '$currentBranch'" }
        [void]$sb.AppendLine("- $($s.repo): $m")
    }
}
Write-TextLf -Path (Join-Path $outRoot "summary.md") -Content $sb.ToString()

# --- Autolimpieza de subcarpetas obsoletas ------------------------------------

Remove-StalePrFolders

# --- Salida por consola -------------------------------------------------------

Write-Host "pr-context :: repo=$repoKey base=$BaseBranch -> $currentBranch" -ForegroundColor Cyan
Write-Host "  $($files.Count) archivos, $chunkIndex chunks en $outRel/chunks/" -ForegroundColor Green
if ($hasUncommitted) { Write-Host "  AVISO: hay cambios sin commitear (fuera del diff)." -ForegroundColor Yellow }
Write-Host "  manifest:  $outRel/manifest.json" -ForegroundColor Green
Write-Host "  cuerpo PR: $outRel/PR_body_tmp.md (lo genera la skill en la Fase C)" -ForegroundColor Green
