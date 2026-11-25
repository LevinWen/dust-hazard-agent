# ============================================================================
# A5 基层安全生产智能体 · Demo 启动脚本
#   1) 拉起本地判定服务（0.0.0.0，页面 + API）
#   2) 探活
#   3) 确认花生壳长期隧道在线，取公网地址
#   4) 打印三个访问入口
# 用法：双击 start-demo.bat，或  powershell -ExecutionPolicy Bypass -File start-demo.ps1
#      加 -NoBrowser 则不自动开浏览器
# ============================================================================
param([switch]$NoBrowser)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Port    = 8791
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir  = Split-Path -Parent $ScriptDir          # 脚本在 app/scripts 下，上一级是 app
$McpDir  = Join-Path $AppDir 'mcp'
$RepoDir = Split-Path -Parent $AppDir
$OutLog = Join-Path $env:TEMP 'a5-demo.out'
$ErrLog = Join-Path $env:TEMP 'a5-demo.err'

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  A5 基层安全生产智能体 · 隐患判定 Demo' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan

# ---------- 1. 本地服务 ----------
$listen = $null
try { $listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue } catch {}
if ($listen) {
    Write-Host ("[1/3] 服务已在运行（PID " + $listen[0].OwningProcess + "），跳过启动")
} else {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host '[1/3] 未找到 python，请先安装 Python 3.8+ 并加入 PATH' -ForegroundColor Red
        exit 1
    }
    Write-Host '[1/3] 启动本地服务…'
    Start-Process -FilePath 'python' `
        -ArgumentList 'http_server.py', '--host', '0.0.0.0', '--port', "$Port" `
        -WorkingDirectory $McpDir -WindowStyle Hidden `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
    Start-Sleep -Seconds 3
}

# ---------- 2. 探活 ----------
$health = $null
for ($i = 0; $i -lt 12; $i++) {
    try {
        $health = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $Port + "/health") -TimeoutSec 4
        break
    } catch { Start-Sleep -Milliseconds 800 }
}
if (-not $health) {
    Write-Host '[2/3] 服务未就绪。最近的错误日志：' -ForegroundColor Red
    if (Test-Path $ErrLog) { Get-Content $ErrLog -Tail 15 }
    Write-Host ("      完整日志：" + $ErrLog)
    exit 1
}
Write-Host ("[2/3] 服务就绪：" + $health.tools + " 个工具 · 引擎版本 " + $health.engine_version)

# ---------- 3. 花生壳隧道 ----------
$Pub = ''
if (-not (Get-Command hsk-cli -ErrorAction SilentlyContinue)) {
    Write-Host '[3/3] 未安装 hsk-cli，公网入口不可用（本机与局域网仍可用）' -ForegroundColor Yellow
} else {
    try {
        $st = ((hsk-cli engine status --format json 2>$null) -join '') | ConvertFrom-Json
        if (-not $st.data.node_online) {
            Write-Host '[3/3] 花生壳引擎未在线，正在拉起…'
            hsk-cli engine ensure --format json 2>$null | Out-Null
        }
        $mm = ((hsk-cli engine mapping list --format json 2>$null) -join '') | ConvertFrom-Json
        if ($mm.data.items -and @($mm.data.items).Count -gt 0) { $Pub = $mm.data.items[0].public_url }
        if ($Pub) { Write-Host ("[3/3] 公网隧道在线：" + $Pub) }
        else { Write-Host '[3/3] 未找到长期映射，公网入口不可用' -ForegroundColor Yellow }
    } catch {
        Write-Host '[3/3] 花生壳状态查询失败，公网入口可能不可用' -ForegroundColor Yellow
    }
}

# ---------- 访问地址 ----------
$ips = @()
try {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -ExpandProperty IPAddress
} catch {}

Write-Host ''
Write-Host '------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host '  打开下面任一地址即可（手机、平板、别的电脑都行）'
Write-Host '------------------------------------------------------------' -ForegroundColor DarkGray
Write-Host ('  本机      http://127.0.0.1:' + $Port + '/')
foreach ($ip in $ips) { Write-Host ('  局域网    http://' + $ip + ':' + $Port + '/') }
if ($Pub) { Write-Host ('  公网      ' + $Pub + '/') -ForegroundColor Green }
Write-Host ''
Write-Host '  停止服务：双击 stop-demo.bat' -ForegroundColor DarkGray
Write-Host ('  服务日志：' + $ErrLog) -ForegroundColor DarkGray
Write-Host ('  公网自测：python app\mcp\tests\test_remote_mcp.py --base ' + $Pub) -ForegroundColor DarkGray
Write-Host ''

if (-not $NoBrowser) {
    try { Start-Process ("http://127.0.0.1:" + $Port + "/") } catch {}
}