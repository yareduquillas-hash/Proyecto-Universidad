# Restauración mínima del piloto (Windows PowerShell).
# Sobreescribe la BD y uploads con el contenido de un backup.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -Dir backup\<fecha>
param(
    [Parameter(Mandatory = $true)]
    [string]$Dir
)
$ErrorActionPreference = "Stop"
# UTF-8: psql debe recibir los bytes del archivo, no una re-encoding con la
# codepage del sistema (rompía á/é/í/ó/ú/ñ en restores de Windows).
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
if (-not (Test-Path $Dir)) { throw "No existe el directorio de backup: $Dir" }
$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "nucleo" }
$pgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "nucleo" }

$dbFile = Join-Path $Dir "db.sql"
if (-not (Test-Path $dbFile)) { throw "Falta $dbFile" }
Write-Output "Restaurando BD desde $dbFile ..."
# ON_ERROR_STOP=1: sin esto psql sigue tras el primer error y reporta éxito
# aunque la restauración quedó a medias (falso positivo).
Get-Content -Path $dbFile -Encoding UTF8 |
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $pgUser $pgDb
if ($LASTEXITCODE -ne 0) { throw "psql falló (exit $LASTEXITCODE): la restauración NO se completó" }

$zip = Join-Path $Dir "uploads.zip"
if (Test-Path $zip) {
    Write-Output "Restaurando uploads desde $zip ..."
    Expand-Archive -Path $zip -DestinationPath . -Force
}
Write-Output "Restauración completada ($Dir)."
