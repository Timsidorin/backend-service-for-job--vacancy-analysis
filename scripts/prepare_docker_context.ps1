# Создаёт build/context без .venv. Из корня: .\scripts\prepare_docker_context.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "pyproject.toml")) { Write-Error "Запускайте из корня репозитория" }

$ctx = "build\context"
if (Test-Path $ctx) { Remove-Item -Recurse -Force $ctx }
New-Item -ItemType Directory -Path $ctx -Force | Out-Null

Copy-Item "pyproject.toml" $ctx
Copy-Item "uv.lock" $ctx
Copy-Item "services" (Join-Path $ctx "services") -Recurse -Force
Copy-Item "libs" (Join-Path $ctx "libs") -Recurse -Force

# Удаляем .venv, .git, __pycache__ из контекста
Get-ChildItem -Path $ctx -Recurse -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq ".venv" -or $_.Name -eq ".git" -or $_.Name -eq "__pycache__" -or $_.Name -eq ".uv" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# .dockerignore внутри контекста — на всякий случай
Set-Content -Path (Join-Path $ctx ".dockerignore") -Value @(".venv", ".git", "__pycache__", ".uv", ".idea")

$sizeMB = [math]::Round((Get-ChildItem $ctx -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Готово: $ctx ($sizeMB MB). Дальше: docker compose up -d --build"
