# ═══════════════════════════════════════════════════════════════════════════
#  AirSense — create the APK signing key + put it in GitHub Secrets (ONE time)
#  Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
#
#  Run: double-click AirSense_SignSetup.bat  (or right-click this file → Run with PowerShell)
#  The key stays on YOUR PC (Documents\AirSense-keys) — keep a backup of it!
# ═══════════════════════════════════════════════════════════════════════════
$ErrorActionPreference = "Stop"
$Repo  = "nikkpap/AirSense"
$Alias = "airsense"
$Dir   = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "AirSense-keys"
$Jks   = Join-Path $Dir "airsense.jks"
$B64F  = Join-Path $Dir "airsense.jks.base64.txt"

function Step($n, $t) { Write-Host "`n[$n/5] $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  !   $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "  X   $t" -ForegroundColor Red; Read-Host "`nPress Enter to close"; exit 1 }

Write-Host "`n  AirSense - APK signing setup" -ForegroundColor Cyan
Write-Host "  Nikolaos K. Paridis (aka nikkpap) - ALU DEV TEAM`n"

# ── 1. keytool (comes with Android Studio / any Java) ──
Step 1 "Looking for keytool (Android Studio / Java)"
$kt = $null
$cands = @(
  "$env:ProgramFiles\Android\Android Studio\jbr\bin\keytool.exe",
  "$env:ProgramFiles\Android\Android Studio\jre\bin\keytool.exe",
  "$env:LOCALAPPDATA\Programs\Android Studio\jbr\bin\keytool.exe",
  "$env:JAVA_HOME\bin\keytool.exe"
)
foreach ($c in $cands) { if ($c -and (Test-Path $c)) { $kt = $c; break } }
if (-not $kt) { $g = Get-Command keytool -ErrorAction SilentlyContinue; if ($g) { $kt = $g.Source } }
if (-not $kt) {
  $kt = Get-ChildItem "$env:ProgramFiles\Android","$env:ProgramFiles\Java","$env:ProgramFiles\Eclipse Adoptium","$env:LOCALAPPDATA\Programs" `
        -Recurse -Filter keytool.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $kt) {
  Warn "keytool not found - installing Java (Temurin 17) with winget..."
  winget install -e --id EclipseAdoptium.Temurin.17.JDK --accept-source-agreements --accept-package-agreements | Out-Host
  $kt = Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Recurse -Filter keytool.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
  if (-not $kt) { Fail "Could not find/install keytool. Install Android Studio and run this again." }
}
Ok $kt

# ── 2. password ──
Step 2 "Password for the key (at least 8 characters - WRITE IT DOWN)"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
if (Test-Path $Jks) {
  Warn "A key already exists: $Jks"
  Warn "It is reused (a NEW key would break updates of the installed app)."
}
while ($true) {
  $p1 = Read-Host "  Password" -AsSecureString
  $p2 = Read-Host "  Again   " -AsSecureString
  $s1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($p1))
  $s2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($p2))
  if ($s1 -ne $s2) { Warn "Not the same - again"; continue }
  if ($s1.Length -lt 8) { Warn "At least 8 characters"; continue }
  if ($s1 -match '["\s]') { Warn "No spaces or quotes please"; continue }
  break
}
$Pw = $s1

# ── 3. create the key (or check the existing one) ──
Step 3 "Signing key airsense.jks"
if (Test-Path $Jks) {
  & $kt -list -keystore $Jks -storepass $Pw -alias $Alias *> $null
  if ($LASTEXITCODE -ne 0) { Fail "Wrong password for the existing key $Jks" }
  Ok "Existing key, password correct"
} else {
  & $kt -genkeypair -v -keystore $Jks -alias $Alias -keyalg RSA -keysize 4096 -validity 36500 `
      -storepass $Pw -keypass $Pw `
      -dname "CN=Nikolaos K. Paridis, OU=ALU DEV TEAM, O=nikkpap, L=Ptolemaida, C=GR" | Out-Null
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Jks)) { Fail "keytool failed" }
  Ok "Created: $Jks (valid 100 years)"
}
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($Jks))
Set-Content -Path $B64F -Value $b64 -NoNewline -Encoding ascii
Ok "Base64 copy: $B64F"

# ── 4. GitHub Secrets ──
Step 4 "GitHub Secrets ($Repo)"
$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
  Warn "GitHub CLI (gh) not found - installing with winget..."
  winget install -e --id GitHub.cli --accept-source-agreements --accept-package-agreements | Out-Host
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
  $gh = Get-Command gh -ErrorAction SilentlyContinue
}
$done = $false
if ($gh) {
  gh auth status *> $null
  if ($LASTEXITCODE -ne 0) {
    Warn "Log in to GitHub (a browser opens - choose GitHub.com, HTTPS, Login with a web browser)"
    gh auth login -h github.com -p https -w
  }
  try {
    gh secret set AIRSENSE_KEYSTORE_B64      -R $Repo --body $b64; if ($LASTEXITCODE) { throw "b64" }
    gh secret set AIRSENSE_KEYSTORE_PASSWORD -R $Repo --body $Pw; if ($LASTEXITCODE) { throw "pw" }
    gh secret set AIRSENSE_KEY_ALIAS         -R $Repo --body $Alias; if ($LASTEXITCODE) { throw "alias" }
    gh secret set AIRSENSE_KEY_PASSWORD      -R $Repo --body $Pw; if ($LASTEXITCODE) { throw "kpw" }
    Ok "4 secrets saved in GitHub"
    $done = $true
  } catch { Warn "gh could not save the secrets ($_) - do it by hand below" }
}
if (-not $done) {
  Set-Clipboard -Value $b64
  Write-Host "`n  Add them by hand: the page opens now -> 'New repository secret' 4 times:" -ForegroundColor Yellow
  Write-Host "   AIRSENSE_KEYSTORE_B64      = (already in the clipboard: Ctrl+V)  - also in $B64F"
  Write-Host "   AIRSENSE_KEYSTORE_PASSWORD = your password"
  Write-Host "   AIRSENSE_KEY_ALIAS         = airsense"
  Write-Host "   AIRSENSE_KEY_PASSWORD      = your password"
  Start-Process "https://github.com/$Repo/settings/secrets/actions"
}

# ── 5. build a signed release ──
Step 5 "Signed APK"
if ($done) {
  $a = Read-Host "  Start a new GitHub build + release now? (Y/n)"
  if ($a -notmatch '^[nN]') {
    gh workflow run build.yml -R $Repo -f release=true
    if ($LASTEXITCODE -eq 0) { Ok "Started - in ~3 min: https://github.com/$Repo/releases/latest  (AirSense-Android_vX.apk, without -debug)" }
  }
} else {
  Write-Host "  After the 4 secrets: GitHub -> Actions -> Build & Release -> Run workflow -> release = true"
}

Write-Host "`n  IMPORTANT" -ForegroundColor Yellow
Write-Host "  - Keep a BACKUP of $Jks and the password (USB stick / cloud). Without them: no more updates of the same app."
Write-Host "  - On the phone: uninstall the old -debug AirSense ONCE, then install the signed APK. After that, updates install over it."
Read-Host "`nPress Enter to close"
