# Third-party setup

These integrations need credentials you have to create yourself — I can't create accounts
on your behalf. Each one is **inert until you supply its credential**, and the app and
server both build, run and demo fully without any of them. Nothing here is a blocker for
showing the product; these turn on real push, real payments, the scanner module and OCR
of scanned documents.

The scanner (#3) needs no account at all.

---

## 1. Firebase Cloud Messaging — push notifications

Two artefacts: one for the app, one for the server. They come from the same project.

### 1a. `google-services.json` (app)

1. Go to <https://console.firebase.google.com> and **Add project**. Name it `NyayaAI`.
   Google Analytics is optional — decline it, it isn't used.
2. In the project, click the **Android** icon to add an app.
3. **Android package name** — must match exactly, and there are three builds. Add each
   as a separate Android app **in the same project**; one download then covers all three:
   - `ai.nyayaai.staging` ← register first, it's what you demo
   - `ai.nyayaai.mock` — needed for CI, which builds the mock flavor
   - `ai.nyayaai` — production, needed before release

   All three are registered on project `nyayaai-aaef7`. If you ever add a flavor, note
   that a variant with no client entry does **not** break the build: its Google Services
   processing task is switched off and that flavor builds without FCM, logging
   `No Firebase client for <package>`. Packages can be added one at a time.

   Apps can also be created without the console, using the service-account key:

   ```
   POST https://firebase.googleapis.com/v1beta1/projects/<project>/androidApps
   {"packageName": "...", "displayName": "..."}
   ```

   and the full `google-services.json` fetched from
   `GET .../androidApps/<appId>/config` — that endpoint already returns **every**
   client in the project, so one call gives the whole file.
4. Skip the SHA-1 step. It's only needed for Google Sign-In and Dynamic Links, neither of
   which this app uses.
5. Download `google-services.json` and put it at:

   ```
   android/app/google-services.json
   ```

6. Rebuild. The Gradle log line `google-services.json not found` disappears, and FCM is
   live. **This file is gitignored** — it isn't a secret exactly, but it identifies your
   project and shouldn't be in a public repo.

### 1b. Service account key (server)

The server sends push via the FCM **HTTP v1** API. The old `key=AAAA…` server key was
decommissioned in 2024 — ignore any tutorial that uses one.

1. Firebase Console → **⚙ Project settings** → **Service accounts**.
2. **Generate new private key** → downloads a JSON file.
3. Save it outside the repo, e.g. `~/.config/nyayaai/firebase-sa.json`, and `chmod 600` it.
   **This one is a real secret** — it can send push to every user of your project.
4. Point the server at it:

   ```bash
   export FIREBASE_PROJECT_ID=your-project-id      # Console → Project settings → General
   export FIREBASE_CREDENTIALS_PATH=$HOME/.config/nyayaai/firebase-sa.json
   export FAKE_MODE=false
   ```

5. Install the auth library:

   ```bash
   cd server && ./.venv/bin/pip install google-auth
   ```

### Testing it

With `FAKE_MODE=true` (the default) every push is logged instead of sent, so you can see
the whole flow working before any of the above:

```bash
cd server && ./.venv/bin/python -m scripts.send_reminders
```

Look for `FAKE PUSH -> …: [hearing_reminder] Hearing tomorrow`. The seed puts a hearing
tomorrow specifically so this has something to send. Run it twice — the second run sends
zero, because a reminder already delivered is never repeated.

For real push, schedule it:

```bash
0 18 * * *  cd /srv/nyayaai && ./.venv/bin/python -m scripts.send_reminders
```

18:00 IST — the evening before, while there's still time to prepare.

**Emulator note:** push needs an emulator image **with Google Play**, not plain AOSP.
`nyaya_pixel` uses `google_apis`, which works.

**Two things that make push look broken when it isn't:**

* `adb shell am force-stop` puts an app in Android's *stopped state*, and FCM will not
  wake it. Test by backgrounding (HOME), not force-stopping.
* Re-running the seed deletes users, which cascades to their device rows — so there is
  nothing to push to until someone signs in again. `send_reminders` reports devices
  reached separately from reminders recorded so this is visible rather than silent.

---

## 2. Razorpay — payments

You need a Razorpay account and its **Key ID** and **Key Secret**. Test keys work
end-to-end with test cards; no money moves.

1. Sign up at <https://dashboard.razorpay.com>.
2. Stay in **Test Mode** (toggle, top of the dashboard) until you're ready to charge.
3. **Settings → API Keys → Generate Test Key**. You get:
   - `rzp_test_XXXXXXXXXXXX` — the Key ID. Public; it ships in the app.
   - a Key Secret — **server only, never in the app.** Anyone with it can create charges.
4. Server:

   ```bash
   export RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXX
   export RAZORPAY_KEY_SECRET=your_secret
   export FAKE_MODE=false
   ```
5. App — put the **Key ID only** in `android/build-logic/.../AndroidApplicationConventionPlugin.kt`,
   in the `staging` flavor's `RAZORPAY_KEY_ID` field (currently `rzp_test_placeholder`).
6. Webhooks — **Settings → Webhooks → Add New Webhook**:
   - URL: `https://your-server/v1/payments/webhook`
   - Active events: `payment.captured`
   - Set a secret, then `export RAZORPAY_WEBHOOK_SECRET=that_secret`

   The webhook is not optional in production. B.10 marks an invoice paid on a verified
   signature **and** the webhook; the webhook is what catches a payment where the app
   died between paying and reporting back.

For **live** mode you must complete KYC (PAN, bank account, business proof). Budget days,
not minutes — start it early if launch depends on it.

Test cards: `4111 1111 1111 1111`, any future expiry, any CVV.
UPI test: `success@razorpay`.

---

## 3. ML Kit document scanner — no account needed

Runs entirely on-device via Play Services. Nothing to sign up for, no key, no quota.

Two requirements:

- **Google Play Services must be present.** Works on the `google_apis` emulator and on
  any retail Android phone; fails on a plain AOSP image. The app handles that failure by
  offering file import rather than a dead button.
- The scanner module downloads on first use unless bundled. The manifest already declares
  `com.google.mlkit.vision.DEPENDENCIES = docscanner`, which ships it with the install —
  so a lawyer in a courthouse basement with no signal can still scan an order sheet.

Nothing scanned leaves the device during scanning. Crop, perspective correction and PDF
assembly are all local; only the finished PDF is uploaded, through the normal B.9 flow.

---

## 4. Google Document AI — OCR for scanned documents

Only needed for documents with **no text layer**: photographs of orders, and the PDFs the
scanner (#3) produces. A PDF downloaded from eCourts already carries its own text and is
extracted locally with pypdf, free and offline — which is most of them.

Without this, a scan uploads and downloads normally but ends `ocr_status = failed` with
the reason recorded in `documents.ocr_error`, and its contents are not searchable.

Create a Document AI processor (type: *Document OCR*) in the GCP console, then a service
account with the *Document AI API User* role, and set on the server:

```
DOCUMENT_AI_PROJECT_ID=your-gcp-project
DOCUMENT_AI_PROCESSOR_ID=abc123def456
DOCUMENT_AI_LOCATION=us          # or eu / asia — must match where you created it
GOOGLE_CREDENTIALS_PATH=/etc/secrets/document-ai.json
```

The location is part of the API hostname as well as the resource path, so a mismatch
reads as a 404 on a processor that plainly exists.

Two things worth knowing before turning it on:

- **It is billed per page**, and Indian court scans are long. `OCR_PROVIDER=none` turns
  extraction off outright if a bill surprises you.
- **A separate service account from Firebase (#1).** Sharing one would give the push
  credential read access to every document a firm has uploaded.

`OCR_PROVIDER=tesseract` selects the local fallback instead — no account, no per-page
cost, worse results. It needs `pip install pytesseract pillow pdf2image` plus the
`tesseract-ocr` and `poppler-utils` system packages, which Render's Python runtime does
not include; the server says so explicitly when they are missing.

---

## What each credential can do if leaked

| Credential | Where it lives | Risk |
|---|---|---|
| `google-services.json` | app, gitignored | Low. Identifies the project; can't send push. |
| Firebase service account | server only | **High.** Sends push to every user. |
| Razorpay Key ID | app | None. Public by design. |
| Razorpay Key Secret | server only | **High.** Can create and capture charges. |
| Razorpay webhook secret | server only | **High.** Forge a webhook, mark invoices paid. |
| Document AI service account | server only | **Medium.** Runs up a per-page bill; reads nothing of ours. |

The three marked high must never reach the repo, the app, or a log line. The server reads
all of them from the environment for that reason.
