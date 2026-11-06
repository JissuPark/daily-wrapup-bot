# wrapup 승인 봇 — Windows(PC) 실행기. 작업 스케줄러가 로그온 때 띄운다.
# - 한 PC 에 하나만 뜬다(이름 있는 Mutex) — 클릭 직렬화 락이 프로세스 안에서만 유효하기 때문.
# - 봇이 죽으면 30초 뒤 다시 띄운다.
# - env 파일 값은 이 프로세스 환경변수로만 넣고 출력하지 않는다.
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $env:USERPROFILE '.config\wrapup-bot\env'
$Log = Join-Path $env:USERPROFILE 'wrapup-bot.log'

$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Local\wrapup-slack-bot', [ref]$created)
if (-not $created) { exit 0 }

function Write-Log($msg) {
    try {
        Add-Content -Path $Log -Encoding utf8 -ErrorAction Stop -Value ("{0} [runner] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
    } catch { }  # 로그를 못 써도 실행기는 계속 돈다
}

if (-not (Test-Path $EnvFile)) { Write-Log "env 파일 없음"; exit 1 }
foreach ($line in Get-Content -Path $EnvFile -Encoding utf8) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line.Split('=', 2)
    [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process')
}
$env:PYTHONIOENCODING = 'utf-8'
$env:WRAPUP_BOT_LOG = $Log
$Python = Join-Path $Repo '.venv\Scripts\python.exe'

try {
    while ($true) {
        Write-Log "봇 시작"
        $p = Start-Process -FilePath $Python -ArgumentList '-m', 'wrapup_bot.app' -WorkingDirectory $Repo `
            -NoNewWindow -PassThru -RedirectStandardOutput "$Log.out" -RedirectStandardError "$Log.err"
        $p.WaitForExit()
        try { Get-Content "$Log.out", "$Log.err" -Encoding utf8 -ErrorAction SilentlyContinue | Add-Content -Path $Log -Encoding utf8 -ErrorAction Stop } catch { }
        Write-Log ("봇 종료 코드 {0} — 30초 뒤 재시작" -f $p.ExitCode)
        Start-Sleep -Seconds 30
    }
} finally {
    $mutex.ReleaseMutex()
}
