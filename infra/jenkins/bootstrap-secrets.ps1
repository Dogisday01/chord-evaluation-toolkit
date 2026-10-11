$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $PSScriptRoot 'secrets'
if (Test-Path -LiteralPath $secretDirectory) {
    throw 'Secrets directory already exists; preserve the current credentials.'
}
$keygen = (Get-Command ssh-keygen.exe -ErrorAction Stop).Source
New-Item -ItemType Directory -Path $secretDirectory | Out-Null
try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $bytes = New-Object byte[] 32
        $random.GetBytes($bytes)
        [System.IO.File]::WriteAllText(
            (Join-Path $secretDirectory 'admin_password.txt'),
            [Convert]::ToBase64String($bytes), $utf8)
    } finally {
        $random.Dispose()
    }
    foreach ($name in @('agent_key', 'agent_host_key')) {
        $keyPath = Join-Path $secretDirectory $name
        if ($keyPath.Contains('"')) { throw 'Unsupported quote in secrets path' }
        # ProcessStartInfo preserves the empty passphrase on Windows PowerShell 5.1.
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = $keygen
        $start.Arguments = '-q -t ed25519 -N "" -f "' + $keyPath + '"'
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $process = [System.Diagnostics.Process]::Start($start)
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw 'SSH key generation failed' }
        $process.Dispose()
    }
    Write-Output 'Created local Jenkins secrets; no credentials were printed.'
} catch {
    throw "Bootstrap incomplete. Preserve and inspect the local secrets directory before retrying. $($_.Exception.Message)"
}
