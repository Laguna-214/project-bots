#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TOOLS=${NATIVE_TOOLS_CACHE:-"${XDG_CACHE_HOME:-$HOME/.cache}/project-bots/native-tools"}
export JAVA_HOME="$TOOLS/jdk-17.0.17+10"
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_HOME="$TOOLS/sdk"
export ANDROID_USER_HOME="$TOOLS/android-user"
export GRADLE_USER_HOME="${NATIVE_GRADLE_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/project-bots/native-gradle}"
export NATIVE_DEBUG_KEYSTORE="$TOOLS/debug.keystore"
umask 077
mkdir -p "$ANDROID_USER_HOME" "$TOOLS/test-classes" "$ROOT/clients/artifacts"
if [ ! -f "$NATIVE_DEBUG_KEYSTORE" ]; then
 "$JAVA_HOME/bin/keytool" -genkeypair -keystore "$NATIVE_DEBUG_KEYSTORE" -storepass android -keypass android -alias androiddebugkey -dname 'CN=Project Bots Debug' -keyalg RSA -keysize 3072 -validity 3650
fi
"$JAVA_HOME/bin/javac" -d "$TOOLS/test-classes" \
 "$ROOT/clients/android/app/src/main/java/app/projectbots/Endpoint.java" \
 "$ROOT/clients/android/app/src/main/java/app/projectbots/NativeTransport.java" \
 "$ROOT/clients/android/app/src/main/java/app/projectbots/SelectionGate.java" \
 "$ROOT/clients/android/app/src/main/java/app/projectbots/HistoryLedger.java" \
 "$ROOT/clients/android/app/src/main/java/app/projectbots/DraftRevision.java" \
 "$ROOT/clients/android/tests/EndpointTest.java" \
 "$ROOT/clients/android/tests/TransportTest.java" \
 "$ROOT/clients/android/tests/SelectionGateTest.java" \
 "$ROOT/clients/android/tests/PresentationStateTest.java" \
 "$ROOT/clients/android/tests/FixtureBridge.java"
"$JAVA_HOME/bin/java" -cp "$TOOLS/test-classes" app.projectbots.EndpointTest
# Desktop JDK suppresses Origin by default; Android's HTTP implementation differs.
# This JVM-only flag tests exact server headers, not Android runtime acceptance.
"$JAVA_HOME/bin/java" -Dsun.net.http.allowRestrictedHeaders=true -cp "$TOOLS/test-classes" app.projectbots.TransportTest
"$JAVA_HOME/bin/java" -cp "$TOOLS/test-classes" app.projectbots.SelectionGateTest
"$JAVA_HOME/bin/java" -cp "$TOOLS/test-classes" app.projectbots.PresentationStateTest
NATIVE_TOOLS_CACHE="$TOOLS" python3 "$ROOT/clients/android/tests/platform_test.py"
python3 "$ROOT/clients/android/tests/security_test.py"
NATIVE_TOOLS_CACHE="$TOOLS" python3 "$ROOT/clients/android/tests/activity_test.py"
cd "$ROOT/clients/android"
"$TOOLS/gradle-8.11.1/bin/gradle" --no-daemon --dependency-verification strict :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
APK="$ROOT/clients/artifacts/ProjectBots-android-debug.apk"
cp app/build/outputs/apk/debug/app-debug.apk "$APK"
TEST_APK="$ROOT/clients/artifacts/ProjectBots-android-regression-test.apk"
cp app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk "$TEST_APK"
"$ANDROID_HOME/build-tools/35.0.0/apksigner" verify --verbose "$TEST_APK"
"$ANDROID_HOME/build-tools/35.0.0/apksigner" verify --verbose "$APK"
"$ANDROID_HOME/build-tools/35.0.0/aapt" dump badging "$APK" > "$ROOT/clients/artifacts/android-badging.txt"
cd "$ROOT/clients/artifacts"
sha256sum ProjectBots-android-debug.apk > ProjectBots-android-debug.apk.sha256
sha256sum ProjectBots-android-regression-test.apk > ProjectBots-android-regression-test.apk.sha256
sha256sum -c ProjectBots-android-debug.apk.sha256
sha256sum -c ProjectBots-android-regression-test.apk.sha256
