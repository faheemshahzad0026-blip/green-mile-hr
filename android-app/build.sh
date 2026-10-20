#!/usr/bin/env bash
set -euo pipefail
: "${GREEN_MILE_ANDROID_SDK:?Set GREEN_MILE_ANDROID_SDK to the Android SDK path}"
: "${GREEN_MILE_SIGNING_KEY:?Set GREEN_MILE_SIGNING_KEY to the signing keystore path}"
: "${GREEN_MILE_KEY_PASSWORD:?Set GREEN_MILE_KEY_PASSWORD to the keystore password}"
root=$(cd "$(dirname "$0")" && pwd)
build="$root/build"
tools="$GREEN_MILE_ANDROID_SDK/build-tools/35.0.0"
platform="$GREEN_MILE_ANDROID_SDK/platforms/android-35/android.jar"
mkdir -p "$build/classes" "$build/dex" "$build/generated"
"$tools/aapt2" compile --dir "$root/res" -o "$build/resources.zip"
"$tools/aapt2" link -o "$build/base.apk" -I "$platform" --manifest "$root/AndroidManifest.xml" --java "$build/generated" "$build/resources.zip"
find "$root/src" "$build/generated" -name '*.java' > "$build/sources.txt"
if command -v javac >/dev/null 2>&1; then
 javac -source 8 -target 8 -bootclasspath "$platform" -d "$build/classes" @"$build/sources.txt"
else
 : "${GREEN_MILE_ECJ_JAR:?Set GREEN_MILE_ECJ_JAR when a JDK compiler is unavailable}"
 java -jar "$GREEN_MILE_ECJ_JAR" -source 8 -target 8 -bootclasspath "$platform" -d "$build/classes" @"$build/sources.txt"
fi
find "$build/classes" -name '*.class' > "$build/classes.txt"
"$tools/d8" --lib "$platform" --min-api 26 --output "$build/dex" @"$build/classes.txt"
python3 - "$build" <<'PY'
import sys,zipfile,os
b=sys.argv[1]
with zipfile.ZipFile(b+'/base.apk','a',zipfile.ZIP_DEFLATED) as z:
 for name in os.listdir(b+'/dex'):
  if name.endswith('.dex'):z.write(b+'/dex/'+name,name)
PY
"$tools/zipalign" -f -p 4 "$build/base.apk" "$build/aligned.apk"
"$tools/apksigner" sign --ks "$GREEN_MILE_SIGNING_KEY" --ks-key-alias greenmile --ks-pass env:GREEN_MILE_KEY_PASSWORD --key-pass env:GREEN_MILE_KEY_PASSWORD --out "$build/Green_Mile_Attendance.apk" "$build/aligned.apk"
"$tools/apksigner" verify --verbose "$build/Green_Mile_Attendance.apk"
