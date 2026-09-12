#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Comprueba los enlaces relativos de la documentacion y, opcionalmente, repara
    los que un archivado de OpenSpec ha dejado apuntando al vacio.

.DESCRIPTION
    Archivar un change mueve su directorio de `openspec/changes/<nombre>/` a
    `openspec/changes/archive/<AAAA-MM-DD>-<nombre>/`, y todo enlace que apuntase
    ahi queda roto sin que nada avise. El 2026-09-12 se encontraron **61 enlaces
    rotos** acumulados de esta forma y de una segunda causa (profundidad relativa
    equivocada). Este script existe para que no se vuelvan a acumular.

    Solo se reparan enlaces cuyo destino corregido **existe**. Un enlace que no
    se puede resolver se reporta y no se toca: adivinar el destino es peor que
    dejarlo roto, porque lo esconde.

.PARAMETER Fix
    Aplica las reparaciones. Sin este flag el script solo informa (modo por
    defecto, apto para usarse como puerta).

.PARAMETER Path
    Raiz del repositorio. Por defecto, el directorio actual.

.PARAMETER MaxDepth
    Cuantos niveles `../` se prueban al reparar una profundidad relativa
    equivocada. Por defecto 3.

.OUTPUTS
    Codigo 0 si no queda ningun enlace roto; 1 si queda alguno.

.EXAMPLE
    pwsh check-doc-links.ps1
    pwsh check-doc-links.ps1 -Fix
#>
[CmdletBinding()]
param(
    [switch]$Fix,
    [string]$Path = '.',
    [int]$MaxDepth = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path $Path).Path

# Documentos que son registro historico fechado: se comprueban pero NUNCA se
# reparan. `prompts.md` transcribe prompts que citan rutas escritas para OTRO
# documento, asi que su enlace "roto" es una cita fiel y corregirlo la falsearia.
$frozen = @('Documentos/prompts.md')

# Carpetas que no son documentacion del repo.
# `openspec/changes/archive/**` queda fuera por la misma razon que `prompts.md`: los
# artefactos de un change archivado describen el mundo tal como estaba al cerrarlo, y
# reapuntar sus enlaces seria reescribir un registro fechado.
$excludedDirs = @('.docs-update', '.pr', 'node_modules', '.git', 'bin', 'obj', '.venv',
                  'openspec/changes/archive')

function Get-DocFiles {
    <#  Todo el markdown del repo salvo lo excluido. La comparacion se hace sobre
        la ruta normalizada a `/`, porque en Windows `$rel` llega con `\` y un
        patron escrito con `/` no casaria nunca -- que es como una exclusion
        puede parecer puesta y no estar surtiendo efecto. #>
    param([string]$Root)
    $out = [System.Collections.Generic.List[string]]::new()
    foreach ($f in (Get-ChildItem -Path $Root -Filter '*.md' -Recurse -File -ErrorAction SilentlyContinue)) {
        $rel = $f.FullName.Substring($Root.Length).Replace([IO.Path]::DirectorySeparatorChar, '/').Trim('/')
        $skip = $false
        foreach ($d in $excludedDirs) {
            if ($rel -eq $d -or $rel.StartsWith("$d/") -or $rel -like "*/$d/*") { $skip = $true; break }
        }
        if (-not $skip) { $out.Add($f.FullName) }
    }
    return $out
}

# Quita los bloques cercados y el codigo en linea ANTES de buscar enlaces.
# Sin esto, PowerShell como `[int]($start / $batchSize)` se lee como un enlace
# markdown y se reporta como roto: es un falso positivo, y un comprobador que
# cria falsos positivos se acaba ignorando, que es como se llega a 61.
function Remove-CodeSpans {
    param([string]$Text)
    # El `\r?` no es opcional: el repo corre con core.autocrlf=true, asi que
    # los ficheros llegan en CRLF y un `$` pelado no casa el cierre de la valla.
    # Sin cierre, el bloque se cuela entero y su codigo se lee como enlaces rotos.
    $noFenced = [regex]::Replace($Text, '(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*\r?$', '')
    return [regex]::Replace($noFenced, '`[^`\r\n]*`', '')
}

function Get-Links {
    param([string]$Text)
    $clean = Remove-CodeSpans $Text
    $rx = [regex]'\]\((?<t>(?!https?:|#|mailto:|data:)[^)#\s]+)'
    foreach ($m in $rx.Matches($clean)) { $m.Groups['t'].Value }
}

function Resolve-Target {
    param([string]$DocDir, [string]$Target)
    $decoded = [uri]::UnescapeDataString($Target)
    $candidate = Join-Path $DocDir $decoded
    try { return (Test-Path -LiteralPath $candidate) } catch { return $false }
}

# --- Mapa de changes archivados: <nombre> -> archive/<fecha>-<nombre> ----------
$archiveMap = @{}
$archiveRoot = Join-Path $root 'openspec/changes/archive'
if (Test-Path $archiveRoot) {
    foreach ($d in Get-ChildItem $archiveRoot -Directory) {
        if ($d.Name -match '^\d{4}-\d{2}-\d{2}-(?<name>.+)$') {
            $archiveMap[$Matches['name']] = $d.Name
        }
    }
}

function Get-Repair {
    <#  Devuelve el destino corregido, o $null si no se puede resolver con
        certeza. Solo se propone lo que EXISTE en disco. #>
    param([string]$DocDir, [string]$Target)

    # Se decodifica SOLO para comprobar existencia en disco; las reparaciones se
    # construyen sobre `$Target` tal cual, de modo que `%20` siga siendo `%20`.
    # Emitir un espacio literal romperia el enlace en la mitad de los renderizadores.
    $decoded = [uri]::UnescapeDataString($Target)

    # (1) Change archivado: openspec/changes/<n>/... -> openspec/changes/archive/<fecha>-<n>/...
    if ($Target -match '(?<pre>.*)openspec/changes/(?<name>[^/]+)/(?<rest>.*)$' -and
        $Matches['name'] -ne 'archive') {
        $name = $Matches['name']
        if ($archiveMap.ContainsKey($name)) {
            $fixed = "$($Matches['pre'])openspec/changes/archive/$($archiveMap[$name])/$($Matches['rest'])"
            if (Resolve-Target $DocDir $fixed) { return $fixed }
        }
    }

    # (2) Profundidad relativa equivocada: probar anadiendo `../`, y aceptar solo
    #     si EXACTAMENTE una profundidad resuelve. Varias coincidencias significan
    #     que el destino es ambiguo, y ahi no se adivina.
    $hits = @()
    for ($i = 1; $i -le $MaxDepth; $i++) {
        $cand = ('../' * $i) + $Target
        if (Resolve-Target $DocDir $cand) { $hits += $cand }
    }
    if ($hits.Count -eq 1) { return $hits[0] }

    return $null
}

# --- Recorrido ---------------------------------------------------------------
$broken = @(); $repaired = @(); $unresolved = @(); $checked = 0

foreach ($full in (Get-DocFiles -Root $root)) {
    $rel = $full.Substring($root.Length).TrimStart('\', '/').Replace('\', '/')
    $docDir = Split-Path $full -Parent
    $text = Get-Content -LiteralPath $full -Raw -Encoding UTF8
    if ([string]::IsNullOrEmpty($text)) { continue }

    $isFrozen = $frozen -contains $rel
    $newText = $text
    $changed = $false

    foreach ($t in (Get-Links $text)) {
        $checked++
        if (Resolve-Target $docDir $t) { continue }

        $broken += [pscustomobject]@{ Doc = $rel; Target = $t }

        if ($isFrozen) {
            $unresolved += [pscustomobject]@{ Doc = $rel; Target = $t; Reason = 'registro historico: no se repara' }
            continue
        }

        $repair = Get-Repair -DocDir $docDir -Target $t
        if ($null -eq $repair) {
            $unresolved += [pscustomobject]@{ Doc = $rel; Target = $t; Reason = 'destino no resoluble' }
            continue
        }

        $repaired += [pscustomobject]@{ Doc = $rel; From = $t; To = $repair }
        if ($Fix) {
            $newText = $newText.Replace("]($t", "]($repair")
            $changed = $true
        }
    }

    if ($Fix -and $changed) {
        Set-Content -LiteralPath $full -Value $newText -Encoding UTF8 -NoNewline
    }
}

# --- Informe -----------------------------------------------------------------
$verb = if ($Fix) { 'reparados' } else { 'reparables' }
Write-Host "check-doc-links :: $checked enlaces relativos comprobados"
Write-Host "  rotos:        $($broken.Count)"
Write-Host "  $verb`:  $($repaired.Count)"
Write-Host "  sin resolver: $($unresolved.Count)"

if ($repaired.Count) {
    Write-Host ''
    Write-Host ($(if ($Fix) { 'Reparados:' } else { 'Reparables (ejecuta con -Fix):' }))
    foreach ($r in $repaired) { Write-Host "  $($r.Doc)`n      $($r.From)`n   -> $($r.To)" }
}

if ($unresolved.Count) {
    Write-Host ''
    Write-Host 'Sin resolver (requieren decision humana):'
    foreach ($u in $unresolved) { Write-Host "  $($u.Doc)`n      $($u.Target)   [$($u.Reason)]" }
}

$remaining = if ($Fix) { $unresolved.Count } else { $broken.Count }
if ($remaining -gt 0) { exit 1 }

Write-Host ''
Write-Host 'Sin enlaces rotos.'
exit 0
