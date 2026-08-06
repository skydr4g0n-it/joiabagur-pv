# =============================================================================
# docs-context.ps1
#
# FASE A del actualizador de documentacion: recopilacion DETERMINISTA de los
# ultimos cambios del repo (commiteados y sin commitear) y de los changes de
# OpenSpec en curso o recien archivados, con la lista de documentos candidatos
# a actualizar segun config/doc-impact.json. No interviene ningun modelo de
# lenguaje en esta fase -> cero alucinacion en la recoleccion.
#
# Produce, en <repo>/.docs-update/<rama>/ :
#   manifest.json   Cambios clasificados por area + documentos candidatos.
#   summary.md      Resumen legible por humanos.
#
# Cada rama tiene su subcarpeta (slug de la rama). Las subcarpetas de ramas que
# ya no existen se podan automaticamente en cada ejecucion (autolimpieza).
#
# La rama base NUNCA se asume: hay que pasarla con -BaseBranch (o un rango
# explicito con -Range). Si falta, el script se detiene, sugiere la que
# detectaria (origin/HEAD) y lista candidatas, para que quien lo invoca
# pregunte al usuario. -AutoBase acepta la sugerencia de forma explicita
# (uso desatendido).
#
# Este script esta replicado en .agent/, .claude/, .codex/, .cursor/ y
# .opencode/skills/update-docs/scripts/. Editar una copia y replicarla al resto.
#
# Uso:
#   ./docs-context.ps1 -BaseBranch <rama> [-NoFetch] [-NoUncommitted]
#   ./docs-context.ps1 -Range HEAD~10..HEAD        # ventana explicita, sin base
#   ./docs-context.ps1 -AutoBase                   # acepta la base detectada
# =============================================================================

[CmdletBinding()]
param(
    [string]$BaseBranch = "",
    [string]$Range = "",
    [string]$OutDir = ".docs-update",
    [int]$RecentArchiveDays = 0,
    [switch]$NoFetch,
    [switch]$AutoBase,
    [switch]$NoUncommitted
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

function Get-CleanPath {
    # git cita las rutas con caracteres especiales: "src/ficheiro con espacio.cs"
    param([string]$Raw)
    $p = $Raw.Trim()
    if ($p.StartsWith('"') -and $p.EndsWith('"')) { $p = $p.Substring(1, $p.Length - 2) }
    return ($p -replace '\\', '/')
}

# --- Localizacion del repo y la configuracion ---------------------------------

$repoRoot = (Invoke-Git @("rev-parse", "--show-toplevel")).Trim()
if (-not $repoRoot) { throw "No estas dentro de un repositorio Git." }
Set-Location $repoRoot

$configPath = Join-Path $PSScriptRoot "../config/doc-impact.json"
if (-not (Test-Path $configPath)) { throw "No se encuentra la matriz de impacto: $configPath" }
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json

if ($RecentArchiveDays -le 0) { $RecentArchiveDays = [int]$config.options.recentArchiveDays }
$maxEvidence = [int]$config.options.maxEvidenceFiles
if ($maxEvidence -le 0) { $maxEvidence = 12 }

$currentBranch = (Invoke-Git @("rev-parse", "--abbrev-ref", "HEAD")).Trim()

# --- Rango de comparacion -----------------------------------------------------

# Base SUGERIDA. Ojo: es solo una sugerencia, no se aplica sola. La rama base la
# decide siempre una persona (misma regla que la skill generate-pr).
function Get-SuggestedBase {
    $head = (Invoke-Git @("rev-parse", "--abbrev-ref", "origin/HEAD") -AllowFail).Trim()
    if ($head -and $head -notmatch "fatal") { return ($head -replace "^origin/", "") }
    if ((Invoke-Git @("rev-parse", "--verify", "origin/main")   -AllowFail) -notmatch "fatal") { return "main" }
    if ((Invoke-Git @("rev-parse", "--verify", "origin/master") -AllowFail) -notmatch "fatal") { return "master" }
    return ""
}

$fromRef   = ""
$toRef     = "HEAD"
$baseRef   = ""
$rangeMode = ""

if ($Range) {
    $rangeMode = "range"
    if ($Range -match '^(.*?)\.\.\.?(.*)$') {
        $fromRef = $Matches[1].Trim()
        if ($Matches[2].Trim()) { $toRef = $Matches[2].Trim() }
    } else {
        $fromRef = $Range.Trim()
    }
    if ((Invoke-Git @("rev-parse", "--verify", $fromRef) -AllowFail) -match "fatal") {
        throw "El rango '-Range $Range' no resuelve: '$fromRef' no es una referencia valida."
    }
} else {
    $rangeMode = "branch-vs-base"
    if (-not $BaseBranch) {
        $suggested = Get-SuggestedBase
        if ($AutoBase) {
            if (-not $suggested) { throw "No se pudo detectar ninguna rama base y no se indico -BaseBranch." }
            $BaseBranch = $suggested
            Write-Host "docs-context :: -AutoBase: se usa la base detectada '$BaseBranch'." -ForegroundColor Yellow
        } else {
            Write-Host ""
            Write-Host "docs-context :: falta la rama base. No se asume ninguna." -ForegroundColor Yellow
            Write-Host "  Rama actual:              $currentBranch" -ForegroundColor DarkGray
            if ($suggested) {
                Write-Host "  Sugerencia (origin/HEAD): $suggested" -ForegroundColor Cyan
            } else {
                Write-Host "  Sin sugerencia: 'origin/HEAD' no esta definido en este clon." -ForegroundColor DarkGray
            }
            $cands = @()
            $remoteRaw = Invoke-Git @("branch", "-r", "--format=%(refname:short)") -AllowFail
            if ($LASTEXITCODE -eq 0) {
                $cands = @($remoteRaw -split "`n" |
                    ForEach-Object { $_.Trim() } |
                    Where-Object { $_ -match '/' } |
                    ForEach-Object { ($_ -split '/', 2)[1] } |
                    Where-Object { $_ -and $_ -ne 'HEAD' -and $_ -ne $currentBranch } |
                    Select-Object -Unique)
            }
            if ($cands.Count -gt 0) {
                Write-Host "  Candidatas:               $($cands -join ', ')" -ForegroundColor Cyan
            }
            Write-Host ""
            Write-Host "  Reejecuta indicando la base:  -BaseBranch <rama>" -ForegroundColor Green
            Write-Host "  O una ventana explicita:      -Range HEAD~10..HEAD" -ForegroundColor DarkGray
            Write-Host ""
            exit 2
        }
    }

    if (-not $NoFetch) {
        Invoke-Git @("fetch", "origin", $BaseBranch, "--quiet") -AllowFail | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "docs-context :: aviso: 'git fetch origin $BaseBranch' fallo; se usa la copia local." -ForegroundColor Yellow
        }
    }

    $baseRef = "origin/$BaseBranch"
    if ((Invoke-Git @("rev-parse", "--verify", $baseRef) -AllowFail) -match "fatal") { $baseRef = $BaseBranch }

    $mergeBaseRaw = Invoke-Git @("merge-base", $baseRef, "HEAD") -AllowFail
    if ($LASTEXITCODE -eq 0) { $fromRef = $mergeBaseRaw.Trim() }
}

# --- Carpeta de salida --------------------------------------------------------

$branchSlug = ($currentBranch -replace '[^\w.-]+', '-').Trim('-')
if (-not $branchSlug) { $branchSlug = "HEAD" }

$docsRoot = Join-Path $repoRoot $OutDir
$outRoot  = Join-Path $docsRoot $branchSlug
$outRel   = "$OutDir/$branchSlug"
if (Test-Path $outRoot) { Remove-Item -Recurse -Force $outRoot }
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

function Remove-StaleFolders {
    if (-not (Test-Path $docsRoot)) { return }
    foreach ($entry in (Get-ChildItem -LiteralPath $docsRoot -Force)) {
        if ($entry.Name -eq $branchSlug) { continue }
        if ($entry.PSIsContainer) {
            $em = Join-Path $entry.FullName "manifest.json"
            if (Test-Path $em) {
                $branch = $null
                try { $branch = (Get-Content -Raw -LiteralPath $em | ConvertFrom-Json).currentBranch } catch { }
                if (-not $branch) { continue }
                & git rev-parse --verify --quiet "refs/heads/$branch" *> $null
                if ($LASTEXITCODE -ne 0) {
                    Remove-Item -Recurse -Force $entry.FullName
                    Write-Host "  autolimpieza: $OutDir/$($entry.Name) eliminada (rama '$branch' ya no existe)" -ForegroundColor DarkGray
                }
            } else {
                Remove-Item -Recurse -Force $entry.FullName
            }
        } else {
            Remove-Item -Force $entry.FullName
        }
    }
}

# --- Recoleccion de ficheros cambiados ----------------------------------------

# Mapa path -> @{ status; origins = @('committed','uncommitted','untracked') }
$fileMap = [ordered]@{}

function Add-ChangedFile {
    param([string]$Path, [string]$Status, [string]$Origin)
    if (-not $Path) { return }
    if (-not $fileMap.Contains($Path)) {
        $fileMap[$Path] = [ordered]@{ path = $Path; status = $Status; origins = @() }
    }
    if ($fileMap[$Path].origins -notcontains $Origin) {
        $fileMap[$Path].origins += $Origin
    }
}

$commits = @()
if ($fromRef) {
    $nameStatus = (Invoke-Git @("diff", "--name-status", $fromRef, $toRef) -AllowFail).Trim()
    if ($LASTEXITCODE -eq 0 -and $nameStatus) {
        foreach ($line in ($nameStatus -split "`n")) {
            if (-not $line.Trim()) { continue }
            $parts = $line -split "`t"
            $status = $parts[0].Substring(0, 1)
            $path = if ($status -eq "R" -and $parts.Count -ge 3) { $parts[2] } else { $parts[1] }
            Add-ChangedFile -Path (Get-CleanPath $path) -Status $status -Origin "committed"
        }
    }

    $logRaw = (Invoke-Git @("log", "$fromRef..$toRef", "--pretty=format:%H%x09%cI%x09%s") -AllowFail).Trim()
    if ($LASTEXITCODE -eq 0 -and $logRaw) {
        foreach ($line in ($logRaw -split "`n")) {
            if (-not $line.Trim()) { continue }
            $p = $line -split "`t", 3
            $commits += [ordered]@{
                hash    = $p[0]
                date    = if ($p.Count -gt 1) { $p[1] } else { "" }
                subject = if ($p.Count -gt 2) { $p[2] } else { "" }
            }
        }
    }
}

$uncommittedCount = 0
if (-not $NoUncommitted) {
    # OJO: nada de .Trim() sobre la salida completa. El formato porcelain usa la
    # columna 1 para el estado del index y la 2 para el del working tree, asi que
    # un fichero solo modificado empieza por espacio (" M ruta"): recortar la
    # cadena entera se comeria ese espacio en la primera linea y, con el, el
    # primer caracter de la ruta.
    $porcelain = Invoke-Git @("status", "--porcelain", "-uall")
    foreach ($rawLine in ($porcelain -split "`n")) {
        $line = $rawLine.TrimEnd("`r", "`n")
        if ($line.Length -lt 4) { continue }
        $code = $line.Substring(0, 2)
        $rest = $line.Substring(3)
        if ($rest -match '^(.*?) -> (.*)$') { $rest = $Matches[2] }   # renombrado
        $path = Get-CleanPath $rest
        if (-not $path) { continue }
        $origin = if ($code -eq "??") { "untracked" } else { "uncommitted" }
        $trimmedCode = $code.Trim()
        $st = if ($code -eq "??") { "A" } elseif ($trimmedCode) { $trimmedCode.Substring(0, 1) } else { "M" }
        Add-ChangedFile -Path $path -Status $st -Origin $origin
        $uncommittedCount++
    }
}

# --- Filtrado de ruido --------------------------------------------------------

$ignoreRegexes = @($config.ignoreGlobs | ForEach-Object { Convert-GlobToRegex $_ })
$ignored = @()
$files = @()
foreach ($key in @($fileMap.Keys)) {
    $entry = $fileMap[$key]
    $skip = $false
    foreach ($rx in $ignoreRegexes) { if ($entry.path -match $rx) { $skip = $true; break } }
    if ($skip) { $ignored += $entry.path } else { $files += $entry }
}

# --- Clasificacion por area ---------------------------------------------------

$activeAreas = @()
foreach ($a in $config.areas) {
    $activeAreas += [pscustomobject]@{
        name    = $a.name
        docs    = @($a.docs)
        reason  = $a.reason
        regexes = @($a.globs | ForEach-Object { Convert-GlobToRegex $_ })
    }
}

function Get-AreaForFile {
    param([string]$Path)
    foreach ($a in $activeAreas) {
        foreach ($rx in $a.regexes) { if ($Path -match $rx) { return $a } }
    }
    return $null
}

$areaHits = [ordered]@{}
$unclassified = @()
foreach ($f in $files) {
    $area = Get-AreaForFile $f.path
    if (-not $area) { $unclassified += $f.path; continue }
    if (-not $areaHits.Contains($area.name)) {
        $areaHits[$area.name] = [ordered]@{ name = $area.name; reason = $area.reason; docs = $area.docs; files = @() }
    }
    $areaHits[$area.name].files += $f.path
}

# --- Documentos candidatos ----------------------------------------------------

$docHits = [ordered]@{}

function Add-DocHit {
    param([string]$DocId, [string]$Reason, [string[]]$Evidence, [string]$Trigger)
    $meta = $config.docs.$DocId
    if (-not $meta) { return }
    if (-not $docHits.Contains($DocId)) {
        $path = $meta.path
        $exists = Test-Path -LiteralPath (Join-Path $repoRoot $path)
        $lastCommit = ""
        $lc = (Invoke-Git @("log", "-1", "--format=%cI", "--", $path) -AllowFail).Trim()
        if ($LASTEXITCODE -eq 0) { $lastCommit = $lc }
        $docHits[$DocId] = [ordered]@{
            id               = $DocId
            path             = $path
            title            = $meta.title
            language         = $meta.language
            policy           = $meta.policy
            alwaysReview     = [bool]$meta.alwaysReview
            reference        = $meta.reference
            note             = $meta.note
            editableSections = @($meta.editableSections)
            frozenSections   = @($meta.frozenSections)
            exists           = $exists
            lastCommit       = $lastCommit
            changedInRange   = $false
            triggers         = @()
            reasons          = @()
            evidence         = @()
        }
    }
    $h = $docHits[$DocId]
    if ($h.triggers -notcontains $Trigger) { $h.triggers += $Trigger }
    if ($Reason -and $h.reasons -notcontains $Reason) { $h.reasons += $Reason }
    foreach ($e in $Evidence) {
        if ($h.evidence.Count -ge $maxEvidence) { break }
        if ($h.evidence -notcontains $e) { $h.evidence += $e }
    }
}

# 1) Documentos que se revisan SIEMPRE (los cinco README del monorepo).
foreach ($prop in $config.docs.PSObject.Properties) {
    if ($prop.Value.alwaysReview) {
        Add-DocHit -DocId $prop.Name -Reason "Revision obligatoria en cada ejecucion de update-docs." -Evidence @() -Trigger "always"
    }
}

# 2) Documentos disparados por las areas tocadas.
foreach ($areaName in $areaHits.Keys) {
    $hit = $areaHits[$areaName]
    foreach ($docId in $hit.docs) {
        Add-DocHit -DocId $docId -Reason $hit.reason -Evidence @($hit.files) -Trigger $areaName
    }
}

# 3) Marca los documentos que el propio rango ya modifico.
$changedPaths = @($files | ForEach-Object { $_.path })
foreach ($docId in @($docHits.Keys)) {
    $dp = $docHits[$docId].path
    $isDir = $dp.EndsWith("/")
    foreach ($cp in $changedPaths) {
        if (($isDir -and $cp.StartsWith($dp)) -or (-not $isDir -and $cp -eq $dp)) {
            $docHits[$docId].changedInRange = $true
            break
        }
    }
}

# --- Changes de OpenSpec ------------------------------------------------------

function Get-ChangeInfo {
    param([string]$Dir, [string]$State)
    $full = Join-Path $repoRoot $Dir
    $artifacts = @()
    foreach ($n in @("proposal.md", "design.md", "tasks.md", "ticket.md", "README.md")) {
        if (Test-Path -LiteralPath (Join-Path $full $n)) { $artifacts += $n }
    }
    $caps = @()
    $specsDir = Join-Path $full "specs"
    if (Test-Path -LiteralPath $specsDir) {
        $caps = @(Get-ChildItem -LiteralPath $specsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
    }
    $done = 0; $pending = 0
    $tasksPath = Join-Path $full "tasks.md"
    if (Test-Path -LiteralPath $tasksPath) {
        $tasksRaw = Get-Content -Raw -LiteralPath $tasksPath
        $done    = ([regex]::Matches($tasksRaw, '(?im)^\s*-\s*\[x\]')).Count
        $pending = ([regex]::Matches($tasksRaw, '(?im)^\s*-\s*\[ \]')).Count
    }
    $created = ""
    $metaPath = Join-Path $full ".openspec.yaml"
    if (Test-Path -LiteralPath $metaPath) {
        $m = Select-String -LiteralPath $metaPath -Pattern '^created:\s*(.+)$' -ErrorAction SilentlyContinue
        if ($m) { $created = $m.Matches[0].Groups[1].Value.Trim() }
    }
    $touched = $false
    foreach ($cp in $changedPaths) { if ($cp.StartsWith($Dir)) { $touched = $true; break } }
    return [ordered]@{
        name          = (Split-Path -Leaf $Dir)
        path          = $Dir
        state         = $State
        created       = $created
        artifacts     = $artifacts
        capabilities  = $caps
        tasksDone     = $done
        tasksPending  = $pending
        touchedInRange = $touched
    }
}

$changes = @()
$changesDir = Join-Path $repoRoot "openspec/changes"
if (Test-Path -LiteralPath $changesDir) {
    foreach ($d in (Get-ChildItem -LiteralPath $changesDir -Directory | Where-Object { $_.Name -ne "archive" })) {
        $changes += Get-ChangeInfo -Dir "openspec/changes/$($d.Name)" -State "active"
    }
    $archiveDir = Join-Path $changesDir "archive"
    if (Test-Path -LiteralPath $archiveDir) {
        $cutoff = (Get-Date).AddDays(-$RecentArchiveDays)
        foreach ($d in (Get-ChildItem -LiteralPath $archiveDir -Directory)) {
            $rel = "openspec/changes/archive/$($d.Name)"
            $isRecent = $false
            if ($d.Name -match '^(\d{4}-\d{2}-\d{2})-') {
                $parsed = [datetime]::MinValue
                if ([datetime]::TryParse($Matches[1], [ref]$parsed)) { $isRecent = ($parsed -ge $cutoff) }
            }
            $isTouched = $false
            foreach ($cp in $changedPaths) { if ($cp.StartsWith($rel)) { $isTouched = $true; break } }
            if ($isRecent -or $isTouched) {
                $changes += Get-ChangeInfo -Dir $rel -State "archived"
            }
        }
    }
}

# --- Manifest -----------------------------------------------------------------

$missingDocs = @($docHits.Keys | Where-Object { -not $docHits[$_].exists } | ForEach-Object { $docHits[$_].path })

$manifest = [ordered]@{
    generatedAt       = (Get-Date).ToString("o")
    outDir            = $outRel
    currentBranch     = $currentBranch
    rangeMode         = $rangeMode
    baseBranch        = $BaseBranch
    baseRef           = $baseRef
    fromRef           = $fromRef
    toRef             = $toRef
    includesUncommitted = (-not $NoUncommitted)
    recentArchiveDays = $RecentArchiveDays
    empty             = ($files.Count -eq 0)
    stats             = [ordered]@{
        filesChanged    = $files.Count
        uncommitted     = $uncommittedCount
        commits         = $commits.Count
        areas           = $areaHits.Count
        docCandidates   = $docHits.Count
        ignoredFiles    = $ignored.Count
    }
    commits           = $commits
    areas             = @($areaHits.Keys | ForEach-Object { $areaHits[$_] })
    docs              = @($docHits.Keys | ForEach-Object { $docHits[$_] })
    missingDocs       = $missingDocs
    unclassifiedFiles = $unclassified
    openspecChanges   = $changes
    files             = $files
}
Write-TextLf -Path (Join-Path $outRoot "manifest.json") -Content ($manifest | ConvertTo-Json -Depth 12)

# --- summary.md ---------------------------------------------------------------

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine("# Contexto de documentacion — joiabagur-pv")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("- Rama actual: ``$currentBranch``")
if ($rangeMode -eq "branch-vs-base") {
    [void]$sb.AppendLine("- Base: ``$BaseBranch`` ($baseRef) — merge-base ``$fromRef``")
} else {
    [void]$sb.AppendLine("- Rango explicito: ``$fromRef..$toRef``")
}
[void]$sb.AppendLine("- Cambios sin commitear incluidos: $(if ($NoUncommitted) { 'no' } else { "si ($uncommittedCount entradas)" })")
[void]$sb.AppendLine("- Ficheros analizados: $($files.Count)  ·  commits: $($commits.Count)  ·  ignorados: $($ignored.Count)")
[void]$sb.AppendLine("")

if ($files.Count -eq 0) {
    [void]$sb.AppendLine("**No hay cambios en el rango indicado.** Nada que documentar.")
} else {
    [void]$sb.AppendLine("## Areas tocadas")
    [void]$sb.AppendLine("")
    foreach ($k in $areaHits.Keys) {
        $a = $areaHits[$k]
        [void]$sb.AppendLine("- **$($a.name)** — $($a.files.Count) fichero(s)")
        [void]$sb.AppendLine("  - $($a.reason)")
    }
    if ($unclassified.Count -gt 0) {
        [void]$sb.AppendLine("- **sin-clasificar** — $($unclassified.Count) fichero(s): revisalos a mano")
    }
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Documentos candidatos")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("| Documento | Politica | Disparado por | Ya tocado | Existe |")
    [void]$sb.AppendLine("|---|---|---|---|---|")
    foreach ($k in $docHits.Keys) {
        $d = $docHits[$k]
        $trig = ($d.triggers -join ", ")
        [void]$sb.AppendLine("| ``$($d.path)`` | $($d.policy) | $trig | $(if ($d.changedInRange) { 'si' } else { 'no' }) | $(if ($d.exists) { 'si' } else { '**NO**' }) |")
    }
    [void]$sb.AppendLine("")
}

if ($missingDocs.Count -gt 0) {
    [void]$sb.AppendLine("## Documentos inexistentes")
    [void]$sb.AppendLine("")
    foreach ($m in $missingDocs) { [void]$sb.AppendLine("- ``$m`` — no existe en el repo: proponer su creacion antes de referenciarlo.") }
    [void]$sb.AppendLine("")
}

if ($changes.Count -gt 0) {
    [void]$sb.AppendLine("## Changes de OpenSpec")
    [void]$sb.AppendLine("")
    foreach ($c in $changes) {
        $tasks = if (($c.tasksDone + $c.tasksPending) -gt 0) { " — tareas $($c.tasksDone)/$($c.tasksDone + $c.tasksPending)" } else { "" }
        $t = if ($c.touchedInRange) { " [tocado en el rango]" } else { "" }
        [void]$sb.AppendLine("- **$($c.name)** ($($c.state))$tasks$t")
        if ($c.capabilities.Count -gt 0) { [void]$sb.AppendLine("  - capabilities: $($c.capabilities -join ', ')") }
        if ($c.artifacts.Count -gt 0)    { [void]$sb.AppendLine("  - artefactos: $($c.artifacts -join ', ')") }
    }
    [void]$sb.AppendLine("")
}

[void]$sb.AppendLine("## Commits ($($commits.Count))")
[void]$sb.AppendLine("")
foreach ($c in $commits) { [void]$sb.AppendLine("- $($c.subject)") }
Write-TextLf -Path (Join-Path $outRoot "summary.md") -Content $sb.ToString()

# --- Cierre -------------------------------------------------------------------

Remove-StaleFolders

Write-Host "docs-context :: rama=$currentBranch modo=$rangeMode" -ForegroundColor Cyan
Write-Host "  $($files.Count) ficheros, $($areaHits.Count) areas, $($docHits.Count) documentos candidatos" -ForegroundColor Green
if ($uncommittedCount -gt 0 -and -not $NoUncommitted) {
    Write-Host "  incluye $uncommittedCount entrada(s) sin commitear" -ForegroundColor Yellow
}
if ($missingDocs.Count -gt 0) {
    Write-Host "  AVISO: documentos inexistentes -> $($missingDocs -join ', ')" -ForegroundColor Yellow
}
Write-Host "  manifest: $outRel/manifest.json" -ForegroundColor Green
Write-Host "  resumen:  $outRel/summary.md" -ForegroundColor Green
Write-Host "  plan:     $outRel/plan.md (lo genera la skill en la Fase C)" -ForegroundColor Green
