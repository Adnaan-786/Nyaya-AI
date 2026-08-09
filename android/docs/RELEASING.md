# Releasing the Android app

## The upload key

Play identifies an app by its signing key. **If you lose it, this `applicationId` can
never be updated again** — not by you, not by anyone, and the only remedy is publishing a
new listing and asking every user to reinstall. Back it up somewhere that survives losing
this laptop, and never commit it.

Generate one, once:

```bash
keytool -genkeypair -v -keystore ~/nyayaai-upload.jks -alias nyayaai -keyalg RSA -keysize 2048 -validity 10000
```

Then create `android/keystore.properties` — gitignored, and worth confirming with
`git check-ignore -v android/keystore.properties` before you paste a password into it:

```properties
storeFile=/Users/you/nyayaai-upload.jks
storePassword=...
keyAlias=nyayaai
keyPassword=...
```

Without that file the release variant still builds, just unsigned. That is deliberate:
CI and anyone who is not publishing should not need the key, and the build should not
fall back to the debug key — an APK signed with it installs perfectly in testing and is
then rejected by Play, long after the build claimed success.

## Building

```bash
./gradlew :app:bundleProdRelease
```

Play wants the `.aab` (`app/build/outputs/bundle/prodRelease/`). Use
`:app:assembleProdRelease` only for an APK you intend to install directly.

**Keep `app/build/outputs/mapping/prodRelease/mapping.txt` for every release you ship.**
R8 obfuscates, so without the mapping file for that exact build, a crash report from the
field is an unreadable list of `a()`, `b()`, `c()`. Upload it to Play alongside the
bundle.

## Why release builds need testing that debug builds do not

`isMinifyEnabled = true` means the release variant runs through R8, which shrinks and
renames everything it cannot prove is needed. Reflection is invisible to it, so the
failure mode is not a build error — it is an APK that installs, launches, and then
throws `ClassNotFoundException` the first time it makes an API call.

`proguard-rules.pro` exists to prevent that, and it is load-bearing: Retrofit's service
interfaces are never implemented in our code, Razorpay calls back into `MainActivity`
by name, and enum constants are resolved from wire strings. Note that a *missing*
`proguardFiles` entry is only a warning — this file was referenced for months before it
existed, and every release built "successfully" that whole time with no keep rules at
all.

So before shipping, install the actual release build and sign in:

```bash
./gradlew :app:assembleStagingRelease
adb install -r app/build/outputs/apk/staging/release/app-staging-release.apk
```

Reaching the OTP screen exercises Retrofit, kotlinx-serialization and the auth flow
under R8 in one go, which is most of the risk. Paying an invoice exercises Razorpay,
which is the rest of it.

## Before the first submission

- `prod` points `BASE_URL` at `https://api.nyayaai.in/v1/`, which does not resolve yet.
  A prod build cannot talk to anything until that DNS exists and serves the API.
- `RAZORPAY_KEY_ID` is `rzp_live_placeholder` in the `prod` flavor.
- `support_phone` in the server's `/app/config` is `+919000000000`, and users see it.
- `versionCode` is `1` and must increase on every upload.
- Play requires a privacy policy URL and a Data safety declaration. This app handles
  privileged client data, so that section needs real care rather than the defaults.
