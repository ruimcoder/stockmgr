# StockMgr Mobile

React Native + Expo companion app for the StockMgr inventory system.

> **Status**: scaffold pending (see GitHub issue #108). The workflows and config files are ready to use once the Expo project is initialised.

---

## Local development setup

### Prerequisites
- Node.js 20+
- [Expo CLI](https://docs.expo.dev/get-started/installation/) — `npm install -g expo-cli`
- [EAS CLI](https://docs.expo.dev/eas/) — `npm install -g eas-cli`
- iOS: Xcode 15+ (macOS only) or use EAS Build in the cloud
- Android: Android Studio or use EAS Build in the cloud

### First run
```sh
cd mobile
npm install
npx expo start
```

Press `i` for iOS simulator, `a` for Android emulator, or scan the QR code with the Expo Go app on your phone.

### Environment
Copy `.env.example` to `.env.local` and fill in your values:
```sh
cp .env.example .env.local
```

---

## Releasing to stores

### Overview of the release pipeline

```
git tag mobile-v1.0.0 → push tag
  → mobile-release.yml triggers
    → EAS Build (cloud build on Expo servers)
      → signed .ipa (iOS) + .aab (Android) artifacts
        → EAS Submit → App Store Connect / Google Play Console
```

---

## Step-by-step: Apple App Store

### 1. Apple Developer account
- Enrol at https://developer.apple.com/programs/ ($99/year)
- Note your **Team ID** from Membership details page

### 2. Create App ID
- In https://developer.apple.com → Certificates, Identifiers & Profiles → Identifiers
- Register a new App ID, Bundle ID: `com.ruimelo.stockmgr` (or your chosen ID — must match `app.json`)

### 3. Create the app in App Store Connect
- Go to https://appstoreconnect.apple.com → Apps → `+`
- Platform: iOS; Bundle ID: the one you registered above
- Copy the **App Store Connect App ID** (numeric, e.g. `6743210987`)

### 4. Update `eas.json`
Replace placeholder values in the `submit.production.ios` block:
```json
"ios": {
  "ascAppId": "6743210987",      ← your App Store Connect App ID
  "appleTeamId": "ABCD1234EF"    ← your Team ID
}
```

### 5. Create an Apple app-specific password
- Go to https://appleid.apple.com → Sign-In and Security → App-Specific Passwords
- Generate a password labelled "EAS Submit"
- Add it to GitHub secrets as `EXPO_APPLE_APP_SPECIFIC_PASSWORD`

### 6. Set up credentials with EAS
```sh
cd mobile
eas credentials --platform ios
```
Choose **"Expo managed"** — EAS generates and manages the distribution certificate and provisioning profile for you. Store them in EAS (the default).

### 7. First submission
The first submission can be done manually or via the workflow:
```sh
cd mobile
eas build --platform ios --profile production
eas submit --platform ios --latest
```

### 8. App Store review
- Add screenshots, description, and metadata in App Store Connect
- Submit for review (typically 1–3 business days)
- After approval, publish from the App Store Connect dashboard

---

## Step-by-step: Google Play Store

### 1. Google Play Developer account
- Register at https://play.google.com/console ($25 one-time fee)

### 2. Create the app in Play Console
- Go to All apps → Create app
- Package name: `com.ruimelo.stockmgr` (must match `app.json`; cannot be changed after publish)

### 3. Create a Google Cloud service account
1. Go to https://console.cloud.google.com → IAM & Admin → Service Accounts
2. Create a new service account (e.g. `eas-submit@<project>.iam.gserviceaccount.com`)
3. Grant role: **none** at project level (permissions are granted in Play Console)
4. Create a JSON key → download the file

### 4. Grant the service account access in Play Console
- In Play Console → Setup → API access → link to Google Cloud project
- Under Service accounts → Grant access to your new service account
- Grant permission: **Release manager** (or "Release apps to testing tracks" minimum)

### 5. Add the key to GitHub secrets
Copy the entire JSON key file content into a GitHub secret named `GOOGLE_SERVICE_ACCOUNT_KEY_JSON`.

### 6. Update `eas.json`
The `submit.production.android` block is already configured to use `./google-service-account.json`. The workflow writes the key file from the secret before calling `eas submit`.

Target track options: `internal` → `alpha` → `beta` → `production`. Start with `internal` (requires individual tester emails).

### 7. First upload — must be manual
Google Play requires the **first** upload to be a complete release done through the Play Console UI:
```sh
cd mobile
eas build --platform android --profile production
```
Download the `.aab` artifact from https://expo.dev, then upload it manually in Play Console → Internal testing → Create new release.

After the first manual upload, all subsequent builds can be automated via `eas submit`.

### 8. Promote to production
From Play Console, promote the release: Internal → Closed testing → Open testing → Production (each step may require a short review).

---

## GitHub secrets reference

Add these in the repository → **Settings → Secrets and variables → Actions**:

| Secret | How to get it |
|--------|---------------|
| `EXPO_TOKEN` | https://expo.dev → Account Settings → Access Tokens → Create token |
| `EXPO_APPLE_APP_SPECIFIC_PASSWORD` | https://appleid.apple.com → App-Specific Passwords |
| `GOOGLE_SERVICE_ACCOUNT_KEY_JSON` | Google Cloud Console → IAM & Admin → Service Accounts → JSON key |

---

## Release workflow

### Automated (recommended)
Tag a commit with the mobile version:
```sh
git tag mobile-v1.0.0
git push origin mobile-v1.0.0
```
This triggers `mobile-release.yml` which builds for both platforms and — if the tag is a version tag — submits to both stores.

### Manual (for individual platform or preview builds)
Run the workflow manually from GitHub → Actions → **Mobile Release** → Run workflow:
- Choose platform: `ios`, `android`, or `all`
- Choose profile: `production` or `preview`
- Choose whether to submit to stores

### Version numbering
Mobile version is separate from web app version:
- `app.json version` — the human-readable semver shown in stores
- `eas.json "autoIncrement": true` — EAS auto-increments the build number on each build

Tag format: `mobile-vMAJOR.MINOR.PATCH` (e.g. `mobile-v1.0.0`)

---

## Expo project ID
After running `eas init` in the `mobile/` directory, replace `REPLACE_WITH_EAS_PROJECT_ID` in `app.json` with the assigned project UUID.
