param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '请先安装 Python 3.12，再运行此脚本。' }
    & $taskPython -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败。' }
}
& $taskPython -X utf8 scripts/configure.py
docker compose up -d --wait
if ($LASTEXITCODE -ne 0) { throw '基础服务启动失败，请检查 Docker Desktop 是否运行。' }
if (-not (Test-Path -LiteralPath 'data/samples/manifest.json')) {
    & $taskPython -X utf8 scripts/collect_samples.py
    if ($LASTEXITCODE -ne 0) { throw '训练素材采集失败。' }
}
if (-not $SkipBuild) {
    if (-not (Test-Path -LiteralPath 'node_modules')) { npm.cmd ci }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败。' }
}
if (-not (Test-Path -LiteralPath 'dist/index.html')) { throw '缺少 dist，请先构建前端。' }
& $taskPython -X utf8 scripts/import_knowledge.py
if ($LASTEXITCODE -ne 0) { throw '知识库初始化失败。' }
$taskHealth = $null
try { $taskHealth = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 } catch {}
if (-not $taskHealth) {
    New-Item -ItemType Directory -Path '.runtime' -Force | Out-Null
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList '-X','utf8','-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot '.runtime/server.log') -RedirectStandardError (Join-Path $PSScriptRoot '.runtime/server-error.log') -PassThru
    $taskProcess.Id | Set-Content -LiteralPath '.runtime/server.pid'
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        Start-Sleep -Seconds 1
        try { $taskHealth=Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; break } catch {}
    }
}
if (-not $taskHealth -or $taskHealth.database -ne 'PostgreSQL + pgvector') { throw '智基服务尚未就绪。请查看 .runtime/server-error.log，并检查 8000 端口。' }
Write-Host '智基已启动：http://127.0.0.1:8000'
Write-Host '账号：xuyihao / zhangxiang / songsang / mengfei；初始密码：123456'
Write-Host '后台管理：user1；初始密码：123456'

