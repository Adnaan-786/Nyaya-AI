# Contributing to nyayaai-android

Part 2 of the NyayaAI build: the Android app and everything the user touches. The server
(Part 1) is a separate repo and a separate team. The seam between us is the Integration
Contract — Section B of the plan, and eventually `openapi.yaml` in the `nyayaai-contract`
repo.

## Local setup

Requires JDK 17 and the Android SDK (`platforms;android-36`, `build-tools;36.0.0`).

```bash
./gradlew assembleMockDebug
```

There is no Gradle install step — use the wrapper. `local.properties` needs `sdk.dir`.

## The gate

Run this before pushing. CI runs exactly the same commands in the same order.

```bash
./gradlew ktlintCheck detekt testDebugUnitTest lintMockDebug assembleMockDebug
```

`./gradlew ktlintFormat` fixes most style failures automatically.

**ktlint and detekt must agree on line length.** `.editorconfig` sets `max_line_length = 120`
to match `MaxLineLength` in `config/detekt/detekt.yml`. If those two ever diverge,
`ktlintFormat` will collapse expressions onto lines detekt then rejects, and the build can
never be both formatted and green.

## Build flavors

| Flavor | Base URL | Data |
|---|---|---|
| `mock` | `http://10.0.2.2:4010/v1/` | JSON fixtures in `app/src/mock/assets/fixtures/` |
| `staging` | `https://staging-api.nyayaai.in/v1/` | Real server, seeded demo data |
| `prod` | `https://api.nyayaai.in/v1/` | Real server |

Combining with Part 1 at the end of the project is selecting the `prod` flavor. That is the
entire integration step, by design — if it ever requires a code change, something has gone
wrong with the contract.

## Working against fixtures (until `openapi.yaml` lands)

The contract exists as prose (Section B) but not yet as a spec, so there is no Prism mock
and no generated DTOs. Instead the `mock` flavor installs an OkHttp interceptor that serves
recorded JSON.

The critical property: fixtures are served **through the real OkHttp stack**, not around
it. JSON parsing, the auth interceptor, the token authenticator and B.3 error mapping all
run exactly as they will against staging. Mock and staging differ only by base URL. A
fake that returned domain objects in-process would make "works on mock" meaningless.

Fixture naming is `<method>_<path with ids collapsed>.json`:

- `POST /v1/auth/otp/verify` → `post_auth_otp_verify.json`
- `GET /v1/cases/{uuid}` → `get_cases_id.json`
- `GET /v1/cases/{uuid}/hearings` → `get_cases_id_hearings.json`

To exercise a B.3 error path, add `<name>__<scenario>.json` and set the
`X-Fixture-Scenario` header. Scenario names map to their real HTTP statuses — see
`FixtureInterceptor.STATUS_BY_SCENARIO`.

## When `openapi.yaml` arrives

1. **Review it the day it drops.** We are the consumer; D.13 makes end of W2 the moment to
   push back, not later. Check the items filed for v1.2: date-only vs instant field types,
   snake_case declared, the optional-field policy, `Idempotency-Key`, and the three missing
   endpoints (`GET /ai/jobs`, a conversations list, `POST /payments/verify`).
2. Generate DTOs into `core/network/dto/` and delete the hand-written ones.
3. **Only the mappers change.** Domain models, repositories, ViewModels and screens stay
   as they are — that separation is why the DTO layer is disposable.
4. Point the `mock` flavor at `prism mock openapi.yaml` on `localhost:4010`, set
   `useFixtures = false`, and re-run the A1 flows unchanged.
5. Any staging response that differs from the spec is filed against the server repo the
   **same day** (D.13). `ApiError.ContractViolation` exists to make those reports specific.

## Architecture rules (D.2 — enforced in review)

- Features depend on `core`, **never on each other**. Cross-feature navigation goes through
  routes. A `feature:*` dependency inside another feature is a blocking review comment.
- Every screen is one `UiState` (Loading / Content / Error / Empty) from a `StateFlow`.
- All I/O lives in repositories. Repositories are Room-first with network refresh (D.11).
- Envelope handling and error mapping live in `core:network` **once**. Nothing outside it
  sees an `ApiEnvelope`, an `HttpException`, or a raw JSON body.

## Two type rules that are not style preferences

**Money is integer paise.** `Paise`, never `Double`. Rs. 1,500.50 is `150050`. Display goes
through `formatRupees()`, which uses Indian lakh/crore grouping (₹1,50,000.00).

**Calendar dates are not instants.** `hearing.date`, `case.next_hearing_date` and
`invoice.due_date` are `CourtDate`, never `Instant`. The contract's "all timestamps are
ISO-8601 UTC" is true of moments and wrong for dates: parse `2026-08-01` as an instant and
any device behind UTC displays 31 July. A lawyer shown the wrong hearing date is the worst
bug this app can have. `IndiaTimeTest` runs with the JVM zone forced to `America/Los_Angeles`
to keep it that way.

## Localization

Every user-visible string lives in `values/` (EN) and `values-hi/` (HI). `HardcodedText` and
`MissingTranslation` are lint **errors** — the build fails, not warns. Hindi tone is
respectful Hinglish where pure Hindi reads awkwardly ("Aaj ki hearings"), per D.4.3, and
needs a review pass by a Hindi-speaking lawyer before release.

## Known constraints

- **AGP stays on 8.13.** AGP 9's new DSL is incompatible with KSP, which Hilt and Room both
  require. This blocks nothing — `targetSdk 36` is what Play requires and 8.13 supports it.
  Revisit when KSP supports AGP 9.
- **Package root is `ai.nyayaai`.** Not `in.nyayaai`: `in` is a Kotlin hard keyword and
  cannot appear in a package name.
