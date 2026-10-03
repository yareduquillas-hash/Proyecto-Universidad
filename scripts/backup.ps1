# Backup mínimo del piloto (Windows PowerShell).
# Respalda PostgreSQL (pg_dump) + carpeta uploads. Salida en backup\<fecha>\.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"
# UTF-8 en consola: sin esto, los acentos (á é í ó ú ñ) del dump se decodifican
# con la codepage del sistema y el restaurar corrompe los datos.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = "backup\$stamp"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
# BD (si cambiaste POSTGRES_USER/DB en .env, ajusta -U y el nombre al final)
# --clean --if-exists: el dump incluye DROP antes de CREATE para que restaurar
# con psql realmente sobrescriba la BD actual (sin esto falla con "already exists").
$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "nucleo" }
$pgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "nucleo" }
$sqlPath = Join-Path $dest "db.sql"
# Capturar y escribir en UTF-8 explícito: el operador `>` de PS 5.1 crea
# archivos UTF-16 que psql no interpreta bien con acentos.
$dump = docker compose exec -T db pg_dump --clean --if-exists -U $pgUser $pgDb
if ($LASTEXITCODE -ne 0) { throw "pg_dump falló (exit $LASTEXITCODE)" }
$text = ($dump | Out-String).TrimEnd("`r", "`n")
if ([string]::IsNullOrWhiteSpace($text)) { throw "pg_dump devolvió un dump vacío" }
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($sqlPath, $text + "`n", $utf8NoBom)
# Uploads (partituras). Se excluyen PDFs de prueba *_test.pdf si quieres con -Exclude.
Compress-Archive -Path "uploads" -DestinationPath "$dest\uploads.zip" -Force
Write-Output "Backup OK en $dest (db.sql + uploads.zip). Guarda esa carpeta fuera del servidor."
