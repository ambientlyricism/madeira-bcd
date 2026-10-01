#!/bin/bash
# Sign the IPA with the owner's certificate and put it in the owner's PRIVATE
# Backblaze B2 bucket for over-the-air install (tap, iOS asks "Install Madeira?").
#
# Runs only when the secrets below exist; otherwise it says so and exits 0, and
# the unsigned IPA artifact is the only output, as before.
#
#   B2_KEY_ID, B2_APP_KEY   Backblaze B2 application key (Read and Write)
#   B2_S3_ENDPOINT          the bucket's S3 endpoint, e.g. s3.eu-central-003.backblazeb2.com
#   B2_SIGN_BUCKET          the PRIVATE bucket: Development.p12 and Development.mobileprovision
#                           at its root; the signed builds go to its ota/ folder
#   SIGN_P12_PASSWORD       the .p12 password
#
# Optional, so the owner need not log in to B2 at all: with these three the
# install page's own 7-day pre-signed link is e-mailed to the owner (Gmail /
# Google Workspace SMTP, STARTTLS on smtp.gmail.com:587). Tapping it in Mail
# opens the page in Safari without any login; "Yükle" installs.
#   OTA_MAIL_USER           the sending Gmail/Workspace address
#   OTA_MAIL_APP_PASSWORD   an app password of that account (not its password)
#   OTA_MAIL_TO             where to send it (usually the same address)
#
# Nothing is public. The IPA, its manifest and kurulum-<version>.html (the install page)
# sit in the private bucket; the page's button and the manifest carry 7-day
# pre-signed URLs, the longest S3 allows. The owner opens kurulum-<version>.html from the
# B2 panel or app and taps "Yükle". The repository and its Actions logs are
# public, so nothing here prints a URL or key material (GitHub masks secrets).
# The certificate files never enter the repository.
#
# The signing mirrors the owner's Feather setup: the app and its extensions
# KEEP their own bundle identifiers (the installed Madeira has the IPA's own
# id, so an OTA install updates it in place and keeps its data); only the
# signature, the embedded profile and the entitlements change, and every
# nested dylib/framework is re-signed. SIGN_USE_PROFILE_BUNDLE_ID=1 instead
# renames them to the profile's App ID (<id>, <id>.<extension suffix>).
#
# Usage: tools/sign-and-publish-ota.sh <unsigned.ipa> <build number>
set -euo pipefail

IPA_IN="$1"
BUILD="$2"

# Cloudflare R2 instead of B2 (owner's decision 2026-09-30: B2's free plan
# allows 1 GB of downloads a day, ~6 installs; R2 charges no egress). When all
# four R2 secrets exist they win; the bucket layout is the same.
#   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
if [ -n "${R2_ACCOUNT_ID:-}" ] && [ -n "${R2_ACCESS_KEY_ID:-}" ] && [ -n "${R2_SECRET_ACCESS_KEY:-}" ] && [ -n "${R2_BUCKET:-}" ]; then
  STORE=R2
  B2_KEY_ID="$R2_ACCESS_KEY_ID" B2_APP_KEY="$R2_SECRET_ACCESS_KEY" B2_SIGN_BUCKET="$R2_BUCKET"
  B2_S3_ENDPOINT="$R2_ACCOUNT_ID.r2.cloudflarestorage.com"
else
  STORE=B2
fi

for v in B2_KEY_ID B2_APP_KEY B2_S3_ENDPOINT B2_SIGN_BUCKET SIGN_P12_PASSWORD; do
  if [ -z "${!v:-}" ]; then
    echo "::notice::OTA signing skipped: secret $v is not set (see tools/sign-and-publish-ota.sh)"
    exit 0
  fi
done
echo "OTA: store $STORE"

W="$RUNNER_TEMP/ota"
rm -rf "$W"; mkdir -p "$W"
if [ "$STORE" = R2 ]; then
  REGION=auto
else
  REGION="$(echo "$B2_S3_ENDPOINT" | sed -n 's/^s3\.\([a-z0-9-]*\)\.backblazeb2\.com$/\1/p')"
  [ -n "$REGION" ] || { echo "::error::OTA: B2_S3_ENDPOINT is not s3.<region>.backblazeb2.com"; exit 1; }
fi
export AWS_ACCESS_KEY_ID="$B2_KEY_ID" AWS_SECRET_ACCESS_KEY="$B2_APP_KEY" AWS_DEFAULT_REGION="$REGION"
# Build 269's IPA upload died on one B2 "InternalError" in UploadPart after the
# CLI's default 2 retries; give transient store errors more room.
export AWS_RETRY_MODE=adaptive AWS_MAX_ATTEMPTS=10
EP="https://$B2_S3_ENDPOINT"
s3() { aws s3 "$@" --endpoint-url "$EP" --only-show-errors; }

# --- certificate and profile from the private bucket ---------------------------
s3 cp "s3://$B2_SIGN_BUCKET/Development.p12" "$W/cert.p12"
s3 cp "s3://$B2_SIGN_BUCKET/Development.mobileprovision" "$W/profile.mobileprovision"

KC="$W/ota.keychain-db"
KCPW="$(uuidgen)"
security create-keychain -p "$KCPW" "$KC"
security set-keychain-settings -lut 3600 "$KC"
security unlock-keychain -p "$KCPW" "$KC"
security import "$W/cert.p12" -k "$KC" -P "$SIGN_P12_PASSWORD" -A -t cert -f pkcs12 >/dev/null
security set-key-partition-list -S apple-tool:,apple: -s -k "$KCPW" "$KC" >/dev/null
security list-keychains -d user -s "$KC" $(security list-keychains -d user | tr -d '"')
trap 'security delete-keychain "$KC" 2>/dev/null || true; rm -rf "$W"' EXIT
IDENTITY="$(security find-identity -v -p codesigning "$KC" | awk 'NR==1 {print $2}')"
[ -n "$IDENTITY" ] || { echo "::error::OTA signing: no code-signing identity in the .p12"; exit 1; }

security cms -D -i "$W/profile.mobileprovision" > "$W/profile.plist"
/usr/libexec/PlistBuddy -x -c "Print :Entitlements" "$W/profile.plist" > "$W/ent.plist"
APPID_FULL="$(/usr/libexec/PlistBuddy -c "Print :Entitlements:application-identifier" "$W/profile.plist")"
TEAM="$(/usr/libexec/PlistBuddy -c "Print :TeamIdentifier:0" "$W/profile.plist")"
BUNDLE_ID="${APPID_FULL#"$TEAM".}"
EXPIRES="$(/usr/libexec/PlistBuddy -c "Print :ExpirationDate" "$W/profile.plist")"
case "$BUNDLE_ID" in
  *\**) echo "::error::OTA signing: a wildcard profile needs an explicit bundle id (not handled yet)"; exit 1 ;;
esac
echo "OTA signing: profile expires $EXPIRES"

# --- re-sign ------------------------------------------------------------------
mkdir -p "$W/x"
ditto -x -k "$IPA_IN" "$W/x"
APP="$(ls -d "$W"/x/Payload/*.app | head -1)"
VERSION="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP/Info.plist" 2>/dev/null || echo "0.1.$BUILD")"

sign() {  # sign <path> [entitlements]
  if [ -n "${2:-}" ]; then
    codesign -f -s "$IDENTITY" --keychain "$KC" --entitlements "$2" --generate-entitlement-der "$1"
  else
    codesign -f -s "$IDENTITY" --keychain "$KC" "$1"
  fi
}

prepare_bundle() {  # prepare_bundle <bundle> <profile-derived id>
  if [ "${SIGN_USE_PROFILE_BUNDLE_ID:-0}" = "1" ]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $2" "$1/Info.plist"
  fi
  rm -rf "$1/_CodeSignature"
  cp "$W/profile.mobileprovision" "$1/embedded.mobileprovision"
}

# Nested code first: every Mach-O dylib and framework anywhere in the bundle.
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q "Mach-O"; then sign "$f"; fi
done < <(find "$APP" \( -name "*.dylib" -o -name "*.so" \) -type f -print0)
while IFS= read -r -d '' fw; do sign "$fw"; done < <(find "$APP" -name "*.framework" -type d -print0 | sort -rz)

# App extensions: <app id>.<their last component>, same profile.
for ex in "$APP"/PlugIns/*.appex "$APP"/Extensions/*.appex; do
  [ -d "$ex" ] || continue
  OLD="$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$ex/Info.plist")"
  prepare_bundle "$ex" "$BUNDLE_ID.${OLD##*.}"
  sign "$ex" "$W/ent.plist"
done

prepare_bundle "$APP" "$BUNDLE_ID"
sign "$APP" "$W/ent.plist"
APP_ID_INSTALLED="$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$APP/Info.plist")"
codesign --verify --deep --strict "$APP"

SIGNED="$W/Madeira-$VERSION.ipa"
(cd "$W/x" && ditto -c -k --keepParent Payload "$SIGNED")

# --- publish (private bucket, pre-signed links) -------------------------------
B="s3://$B2_SIGN_BUCKET/ota"
TTL=604800   # 7 days, the S3 maximum for a pre-signed URL
presign() { aws s3 presign "$1" --expires-in "$TTL" --endpoint-url "$EP"; }

# Storage budget (owner, 2026-10-01: R2's free plan stores 10 GB -- never go
# past it). The WHOLE bucket (signing files and anything else in it included)
# stays under OTA_BUDGET_GB, default 8 (decimal GB, 2 GB headroom), and at most
# ten builds are kept. Room for the new IPA is made BEFORE it is uploaded, so
# the bucket never holds more than the budget even for a moment; the oldest
# builds go first, the one being published never. Older builds stay in the
# Actions artifacts. Prints only version numbers and sizes.
BUDGET_GB="${OTA_BUDGET_GB:-8}"
KEEP_BUILDS=10
prune() {  # $1 = bytes about to be added; makes room, sets USED/LIMIT/BUILDS
  local plan="$W/prune.txt"
  # (no s3() here: `aws s3 ls` rejects --only-show-errors, which silently skipped the cleanup through build 262)
  if ! aws s3 ls "s3://$B2_SIGN_BUCKET/" --recursive --endpoint-url "$EP" > "$W/bucket.txt"; then
    echo "::warning::OTA: could not list the bucket, storage budget not checked"
    USED=0 LIMIT=0 BUILDS=0
    return 0
  fi
  python3 - "$1" "$BUDGET_GB" "$KEEP_BUILDS" "$VERSION" "$W/bucket.txt" > "$plan" <<'PY'
import re, sys
reserve, budget, keep, cur = int(sys.argv[1]), int(float(sys.argv[2]) * 1e9), int(sys.argv[3]), sys.argv[4]
objs = {}
for line in open(sys.argv[5]):
    p = line.rstrip("\n").split(None, 3)   # date time size key
    if len(p) == 4 and p[2].isdigit():
        objs[p[3]] = int(p[2])
size = lambda v: objs.get(f"ota/Madeira-{v}.ipa", 0) + objs.get(f"ota/manifest-{v}.plist", 0) + objs.get(f"kurulum-{v}.html", 0)
key = lambda v: [int(x) for x in re.findall(r"[0-9]+", v)]
vers = sorted((k[len("ota/Madeira-"):-len(".ipa")] for k in objs if re.match(r"^ota/Madeira-.*[.]ipa$", k)), key=key)
total = sum(objs.values())
builds = len(vers)
if reserve:
    if cur in vers:          # re-publishing the same version replaces it
        total -= objs[f"ota/Madeira-{cur}.ipa"]
    else:
        builds += 1
    total += reserve
for v in vers:
    if v == cur:
        continue
    if builds <= keep and total <= budget:
        break
    print(v)
    total -= size(v)
    builds -= 1
print(f"#total {total} {budget} {builds}")
PY
  local v
  for v in $(grep -v '^#' "$plan" || true); do
    s3 rm "$B/Madeira-$v.ipa" || true
    s3 rm "$B/manifest-$v.plist" || true
    s3 rm "s3://$B2_SIGN_BUCKET/kurulum-$v.html" || true
    echo "OTA: removed build $v from the bucket (keep $KEEP_BUILDS builds, budget $BUDGET_GB GB)"
  done
  read -r _ USED LIMIT BUILDS < <(grep '^#total' "$plan") || true
}

SIGNED_BYTES="$(stat -f%z "$SIGNED" 2>/dev/null || stat -c%s "$SIGNED")"
prune "$SIGNED_BYTES"
if [ "${LIMIT:-0}" -gt 0 ] && [ "$USED" -gt "$LIMIT" ]; then
  echo "::error::OTA: the bucket would hold $((USED / 1000000)) MB with this build, over the $BUDGET_GB GB budget even after removing old builds -- not uploading (look for other files in the bucket)"
  exit 1
fi

s3 cp "$SIGNED" "$B/Madeira-$VERSION.ipa" --content-type application/octet-stream
IPA_URL="$(presign "$B/Madeira-$VERSION.ipa")"
IPA_URL_XML="$(python3 -c 'import sys, html; print(html.escape(sys.argv[1]))' "$IPA_URL")"

cat > "$W/manifest.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>items</key>
  <array>
    <dict>
      <key>assets</key>
      <array>
        <dict>
          <key>kind</key><string>software-package</string>
          <key>url</key><string>$IPA_URL_XML</string>
        </dict>
      </array>
      <key>metadata</key>
      <dict>
        <key>bundle-identifier</key><string>$APP_ID_INSTALLED</string>
        <key>bundle-version</key><string>$VERSION</string>
        <key>kind</key><string>software</string>
        <key>title</key><string>Madeira $VERSION</string>
      </dict>
    </dict>
  </array>
</dict>
</plist>
EOF
s3 cp "$W/manifest.plist" "$B/manifest-$VERSION.plist" --content-type application/xml
MANIFEST_URL="$(presign "$B/manifest-$VERSION.plist")"
ENC="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$MANIFEST_URL")"
UNTIL="$(date -u -v+7d '+%Y-%m-%d %H:%M UTC' 2>/dev/null || date -u -d '+7 days' '+%Y-%m-%d %H:%M UTC')"

cat > "$W/kurulum-$VERSION.html" <<EOF
<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Madeira $VERSION</title>
<style>
body{font-family:-apple-system,system-ui,sans-serif;background:#111;color:#eee;display:flex;min-height:100vh;
align-items:center;justify-content:center;margin:0;padding:16px}
.c{text-align:center;max-width:420px}
a.b{display:inline-block;margin-top:18px;padding:14px 28px;border-radius:12px;background:#0a84ff;color:#fff;
text-decoration:none;font-size:18px;font-weight:600}
p{color:#aaa;font-size:14px}
</style></head>
<body><div class="c">
<h1>Madeira $VERSION</h1>
<p>Build $BUILD &middot; $(date -u '+%Y-%m-%d %H:%M UTC')</p>
<a class="b" href="itms-services://?action=download-manifest&amp;url=$ENC">Yükle</a>
<p>Dokun, ardından "Yükle"yi onayla. Link $UNTIL tarihine kadar geçerli.</p>
</div></body></html>
EOF
s3 cp "$W/kurulum-$VERSION.html" "s3://$B2_SIGN_BUCKET/kurulum-$VERSION.html" --content-type "text/html; charset=utf-8" --cache-control no-cache

# Final check (the manifest and page are a few KB); nothing left to remove normally.
prune 0
if [ "${LIMIT:-0}" -gt 0 ]; then
  echo "::notice::OTA: bucket holds $BUILDS builds, $(python3 -c "import sys; print(f'{int(sys.argv[1])/1e9:.2f}')" "$USED") GB of the $BUDGET_GB GB budget"
fi

echo "::notice::OTA: Madeira $VERSION signed (profile expires $EXPIRES); kurulum-$VERSION.html written to the private $STORE bucket (links valid until $UNTIL)"

# --- e-mail the install page's link (optional) -----------------------------------
if [ -n "${OTA_MAIL_USER:-}" ] && [ -n "${OTA_MAIL_APP_PASSWORD:-}" ] && [ -n "${OTA_MAIL_TO:-}" ]; then
  PAGE_URL="$(presign "s3://$B2_SIGN_BUCKET/kurulum-$VERSION.html")"
  if PAGE_URL="$PAGE_URL" VERSION="$VERSION" BUILD="$BUILD" UNTIL="$UNTIL" python3 - <<'PY'
import html, os, smtplib, ssl
from email.message import EmailMessage
v, b, until, url = os.environ["VERSION"], os.environ["BUILD"], os.environ["UNTIL"], os.environ["PAGE_URL"]
m = EmailMessage()
m["Subject"] = f"Madeira {v} kuruluma hazır"
m["From"] = os.environ["OTA_MAIL_USER"]
m["To"] = os.environ["OTA_MAIL_TO"]
m.set_content(f"Madeira {v} (build {b}) imzalandı.\n\nKurulum sayfası (iPhone'da aç, \"Yükle\"ye dokun):\n{url}\n\nLink {until} tarihine kadar geçerli.\n")
m.add_alternative(
    f'<p>Madeira <b>{html.escape(v)}</b> (build {html.escape(b)}) imzalandı.</p>'
    f'<p><a href="{html.escape(url)}" style="display:inline-block;padding:12px 24px;border-radius:10px;'
    f'background:#0a84ff;color:#fff;text-decoration:none;font-weight:600">Kurulum sayfasını aç</a></p>'
    f'<p style="color:#888">Açılan sayfada "Yükle"ye dokun. Link {html.escape(until)} tarihine kadar geçerli.</p>',
    subtype="html")
with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as s:
    s.starttls(context=ssl.create_default_context())
    s.login(os.environ["OTA_MAIL_USER"], os.environ["OTA_MAIL_APP_PASSWORD"])
    s.send_message(m)
PY
  then
    echo "::notice::OTA: install link for $VERSION e-mailed to the owner"
  else
    echo "::warning::OTA: e-mailing the install link failed (check OTA_MAIL_* secrets; the page is still in the bucket)"
  fi
else
  echo "OTA: no OTA_MAIL_* secrets -- install page only in the bucket"
fi
