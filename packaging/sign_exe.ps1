<#
.SYNOPSIS
  Signs the built standalone .exe with a local, self-signed code-signing
  certificate.

.DESCRIPTION
  Generates a self-signed code-signing certificate the first time it's run
  (saved under packaging/codesign/, gitignored) and reuses that same
  certificate on every later run, so every build carries a consistent
  publisher identity instead of a new throwaway one each time.

  IMPORTANT LIMITATION: a self-signed certificate does not make Windows
  SmartScreen trust this app on a machine that has never been told to
  trust this specific certificate. It proves the exe hasn't been altered
  since it was signed and gives it a consistent, verifiable identity
  release-to-release -- but a machine seeing this app for the first time
  will still show a "Windows protected your PC" prompt; the person running
  it clicks "More info" -> "Run anyway" once. Only a certificate from a
  recognized certificate authority avoids that warning on machines you
  don't control (see README.md's "Standalone Windows build" section).

  If you want to stop seeing the warning on machines you *do* control
  (yours, a coworker's), import the exported public certificate
  (packaging/codesign/AlcoholLabelVerification.cer) into that machine's
  Trusted Root Certification Authorities store.

.EXAMPLE
  pyinstaller desktop_app.spec
  powershell -ExecutionPolicy Bypass -File packaging/sign_exe.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ExePath = Join-Path $RepoRoot "dist\AlcoholLabelVerification\AlcoholLabelVerification.exe"
$CodesignDir = Join-Path $PSScriptRoot "codesign"
$PfxPath = Join-Path $CodesignDir "AlcoholLabelVerification.pfx"
$CerPath = Join-Path $CodesignDir "AlcoholLabelVerification.cer"
$PasswordPath = Join-Path $CodesignDir "cert_password.txt"

if (-not (Test-Path $ExePath)) {
    throw "Built exe not found at $ExePath -- run 'pyinstaller desktop_app.spec' first."
}

New-Item -ItemType Directory -Force -Path $CodesignDir | Out-Null

if (-not (Test-Path $PfxPath)) {
    Write-Host "No signing certificate found yet -- generating one."
    Write-Host "It'll be saved under $CodesignDir and reused for every future build."

    $tempCert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=Alcohol Label Verification" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyUsage DigitalSignature `
        -NotAfter (Get-Date).AddYears(5) `
        -FriendlyName "Alcohol Label Verification (self-signed)"

    $password = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    Set-Content -Path $PasswordPath -Value $password -NoNewline
    $securePassword = ConvertTo-SecureString -String $password -Force -AsPlainText

    Export-PfxCertificate -Cert $tempCert -FilePath $PfxPath -Password $securePassword | Out-Null
    Export-Certificate -Cert $tempCert -FilePath $CerPath | Out-Null
    Remove-Item -Path "Cert:\CurrentUser\My\$($tempCert.Thumbprint)" -Force

    Write-Host ""
    Write-Host "Generated: $PfxPath (used to sign builds)"
    Write-Host "Exported:  $CerPath (the public certificate -- import this into"
    Write-Host "           Trusted Root Certification Authorities on any machine"
    Write-Host "           you want to stop seeing the SmartScreen warning on)"
    Write-Host ""
}

$password = Get-Content -Path $PasswordPath -Raw
$securePassword = ConvertTo-SecureString -String $password -Force -AsPlainText
$cert = Import-PfxCertificate -FilePath $PfxPath -CertStoreLocation "Cert:\CurrentUser\My" -Password $securePassword

try {
    $signature = Set-AuthenticodeSignature -FilePath $ExePath -Certificate $cert -TimestampServer "http://timestamp.digicert.com"
} catch {
    Write-Host "Timestamp server unreachable -- signing without a timestamp (the signature will stop validating once the certificate expires)."
    $signature = Set-AuthenticodeSignature -FilePath $ExePath -Certificate $cert
}

# A self-signed certificate's chain terminates at itself rather than a
# root Windows already trusts, so Set-AuthenticodeSignature reports
# "UnknownError" / "A certificate chain processed, but terminated in a
# root certificate which is not trusted by the trust provider" even on a
# fully successful signing -- that's expected here, not a real failure
# (confirmed below via SignerCertificate, not the trust Status). Anything
# else (e.g. "HashMismatch", "NotSigned") means signing genuinely failed.
$untrustedRootExpected = ($signature.Status -eq "UnknownError") -and
    ($signature.StatusMessage -match "not trusted by the trust provider")

if ($signature.Status -ne "Valid" -and -not $untrustedRootExpected) {
    throw "Signing failed ($($signature.Status)): $($signature.StatusMessage)"
}

Write-Host "Signed $ExePath"
Write-Host "Signed by: $($signature.SignerCertificate.Subject)"
if ($signature.Status -eq "Valid") {
    Write-Host "Trust status: Valid (this certificate is already trusted on this machine)"
} else {
    Write-Host "Trust status: not yet trusted on this machine -- expected for a self-signed"
    Write-Host "certificate. The exe IS signed; Windows just won't show it as trusted here"
    Write-Host "(or on any other machine) until that machine imports"
    Write-Host "$CerPath into Trusted Root Certification Authorities."
}
