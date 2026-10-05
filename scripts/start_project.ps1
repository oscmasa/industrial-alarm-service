#Requires -Version 5.1
<#
.SYNOPSIS
Build and initialize the local alarm platform with Docker Compose.
.DESCRIPTION
Apply migrations, seed the catalog and import the committed sample.
Each default run creates a new import audit; existing alarms are deduplicated.
Use -SkipImport when the database already contains the desired events.
#>
[CmdletBinding()]
param([switch]$SkipImport)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$datasetDirectory = Join-Path $projectRoot 'datasets\raw'
$datasetFile = Join-Path $datasetDirectory 'alarms.csv'

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed (exit $LASTEXITCODE): docker $($Arguments -join ' ')"
    }
}

Push-Location -LiteralPath $projectRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker was not found. Install Docker Desktop and open a new terminal.'
    }
    if (-not $SkipImport -and -not (Test-Path -LiteralPath $datasetFile -PathType Leaf)) {
        throw "Dataset not found: $datasetFile"
    }

    Write-Host 'Checking Docker Compose and engine...'
    Invoke-Docker -Arguments @('compose', 'version')
    $engineType = Invoke-Docker -Arguments @('info', '--format', '{{.OSType}}')
    if (($engineType -join '').Trim() -ne 'linux') {
        throw 'Docker must be running in Linux container mode.'
    }

    Write-Host 'Building and starting frontend, API and database...'
    Invoke-Docker -Arguments @('compose', 'up', '--build', '-d', '--wait')

    Write-Host 'Applying database migrations...'
    Invoke-Docker -Arguments @('compose', 'exec', '-T', 'api', 'python', '-m', 'alembic', 'upgrade', 'head')

    Write-Host 'Loading equipment and tags...'
    Invoke-Docker -Arguments @('compose', 'exec', '-T', 'api', 'python', '-m', 'alarm_service.infrastructure.database.seed')

    if (-not $SkipImport) {
        Write-Host 'Importing alarms.csv (a new audit is created; existing alarms are deduplicated)...'
        Invoke-Docker -Arguments @(
            'compose', 'run', '--rm', '-T',
            '--volume', "${datasetDirectory}:/data:ro",
            'api', 'python', '-m', 'alarm_service.cli',
            '--input', '/data/alarms.csv', '--batch-size', '1000'
        )
    }

    $frontendAddress = Invoke-Docker -Arguments @('compose', 'port', 'frontend', '8080')
    $apiAddress = Invoke-Docker -Arguments @('compose', 'port', 'api', '8000')
    Write-Host ''
    Write-Host 'Project ready.'
    Write-Host "Dashboard: http://$($frontendAddress -join '')"
    Write-Host "API docs:  http://$($apiAddress -join '')/docs"
    Write-Host 'Stop services with: docker compose down'
}
catch {
    Write-Error "Startup stopped. $($_.Exception.Message) Open Docker Desktop if it is not running. Inspect services with: docker compose ps; docker compose logs api db frontend" -ErrorAction Continue
    exit 1
}
finally {
    Pop-Location
}
