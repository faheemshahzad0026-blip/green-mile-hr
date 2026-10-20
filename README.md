# Green Mile HR

Private HR management and employee attendance platform for **Green Mile Recycling LLC**, designed for desktop and mobile use in the UAE.

The repository contains the complete web application, Cloudflare database migrations, automated checks, Progressive Web App assets, and the source code for the Android attendance application.

> This is a private business application. Do not commit production passwords, API keys, employee documents, database exports, attendance selfies, or signing keys.

## Application overview

Green Mile HR provides one central workspace for HR administration, employee records, attendance, payroll preparation, document monitoring, employee requests, reporting, and mobile self-service.

### HR administration

- Employee onboarding and employee file management
- Automatic employee code generation
- Departments, designations, work locations, contracts, managers, and employment status
- Employee profile photographs
- Document records and expiry monitoring
- Passport, visa, Emirates ID, labour card, work permit, insurance, driving licence, and contract tracking
- Global search, data-quality review, audit history, JSON backup, and controlled deletion
- Demo-data cleanup with review and confirmation

### Attendance and leave

- Manual attendance and employee mobile check-in/check-out
- Dubai server time and cross-midnight shift handling
- GPS policy and optional office geofence
- Fresh JPEG selfie evidence for every mobile punch
- Attendance summaries and monthly attendance ledger
- Attendance-correction requests
- Leave requests, approvals, and annual leave balances
- Monthly selfie-retention workflow while keeping attendance records

### Payroll and employee lifecycle

- Monthly payroll drafts and payroll review
- Salary components, additions, deductions, overtime, and loan recovery
- Salary payment report and employee salary slips
- Resignations, exit reporting, final settlement, and gratuity guidance
- Automatic mobile-access closure after approved or paid final settlement

### Employee self-service

- Employee ID and six-digit PIN access
- Profile, attendance, leave, approved salary, adjustments, documents, shifts, and assigned assets
- Leave, attendance-correction, certificate, help-desk, and resignation requests
- Announcements and employee notifications
- PIN change, session revocation, rate limiting, and account disable/delete controls

### Reporting and export

- PDF-ready browser print views
- Excel workbooks generated with ExcelJS
- Attendance, payroll, settlement, loan, salary-payment, expiry, and data-quality reports
- Professional Green Mile branding and company logo

## Languages used

| Language / format | Purpose |
|---|---|
| TypeScript | Main web application, API routes, HR business rules, database access, and automated checks |
| TSX / React | Desktop and mobile user interfaces |
| CSS | Responsive Green Mile design system and print layouts |
| SQL | Cloudflare D1 schema migrations and queries |
| Java | Android WebView attendance application |
| JavaScript / MJS | Build scripts, validation checks, and connector tooling |
| Shell | Installation, build, and Android packaging scripts |
| JSON | PWA manifest, configuration, and package metadata |

## Technology stack

| Layer | Technology |
|---|---|
| Web framework | Next.js 16 with React 19 |
| Cloud runtime | Cloudflare Workers through Vinext, Vite, and Wrangler |
| Programming language | TypeScript 5 |
| UI | React, Tailwind CSS 4, Radix UI, Base UI, and shadcn components |
| Forms and validation | React Hook Form, Zod, and Hookform Resolvers |
| Database | Cloudflare D1 (SQLite) |
| ORM and migrations | Drizzle ORM and Drizzle Kit |
| Object storage | Cloudflare R2 |
| Spreadsheet export | ExcelJS |
| Charts | Recharts |
| Dates | date-fns |
| Notifications | Web Push / VAPID and Sonner |
| Icons | Lucide React |
| PWA | Web App Manifest and service worker |
| Android client | Java 17, Android SDK 35, restricted WebView |
| Package manager | pnpm 11 |
| Runtime | Node.js 22.13 or newer |
| Code quality | ESLint 9 and TypeScript compiler |

## High-level architecture

```text
Desktop / Mobile Browser / Android WebView
                    |
           Next.js + React interface
                    |
             Server API routes
              /             \
     Cloudflare D1         Cloudflare R2
   HR and audit data    Photos and selfies
```

The administrator interface and employee gateway use the same HR database. Every record is scoped to its owner. Employee mobile sessions are linked to an existing employee and cannot select another employee when submitting attendance.

## Repository structure

```text
app/                 Pages, admin UI, employee UI, and API routes
components/          Shared interface components
lib/                 HR, attendance, payroll, security, and reporting logic
db/                  Drizzle database schema and database client
drizzle/             Versioned Cloudflare D1 migrations
checks/              Automated business-rule and route checks
public/              Logo, PWA files, icons, and Android APK
android-app/         Android Java source, manifest, resources, and build script
scripts/             Install, development, build, and deployment helpers
build/               Cloudflare/Vinext build integration
vendor/              Retained third-party styles and licence information
examples/             Small D1 integration example
```

## Prerequisites

- Node.js **22.13+**
- pnpm **11.25+**
- Access to the configured Cloudflare/Sites environment
- Cloudflare D1 binding named `DB`
- Cloudflare R2 binding named `BUCKET`

For the Android build:

- Java 17 / JDK
- Android SDK Platform 35
- Android Build Tools 35.0.0
- Private Android signing key for release updates

## Local development

1. Clone the private repository.

   ```bash
   git clone https://github.com/faheemshahzad0026-blip/green-mile-hr.git
   cd green-mile-hr
   ```

2. Install dependencies.

   ```bash
   pnpm run install:ci
   ```

3. Start the development environment.

   ```bash
   pnpm dev
   ```

4. Create a production build.

   ```bash
   pnpm build
   ```

5. Run the local Cloudflare worker build.

   ```bash
   pnpm start
   ```

The application depends on platform-provided authentication and Cloudflare bindings. A plain local browser run without those bindings will not provide the complete production login, D1, R2, or employee-gateway behaviour.

## Runtime bindings and secrets

Configure secrets only in the deployment environment. Never place real values in Git.

| Name | Type | Purpose |
|---|---|---|
| `DB` | D1 binding | HR records, audit history, admin sessions, mobile accounts, and requests |
| `BUCKET` | R2 binding | Profile photographs and attendance selfies |
| `ATTENDANCE_BRIDGE_SECRET` | Secret | Protects the employee attendance bridge |
| `ADMIN_SITE_ACCESS_TOKEN` | Secret, when used | Private server-to-server access to the admin Site |
| `HR_PUSH_PUBLIC_KEY` | Secret/config | Public VAPID key for admin push notifications |
| `HR_PUSH_PRIVATE_KEY` | Secret | Private VAPID key |
| `HR_PUSH_SUBJECT` | Config | VAPID contact subject |

The Android signing key and password are also private and are excluded from Git.

## Database

The production database uses Cloudflare D1, which is SQLite-compatible. Drizzle schema definitions are in `db/schema.ts`, and committed migrations are stored in `drizzle/`.

Core tables include:

- `hr_records` — owner-scoped HR records
- `hr_audit` — record activity and deletion history
- `mobile_accounts` — employee mobile account state and PIN hashes
- `mobile_sessions` — hashed employee session tokens
- Admin login/session, push-subscription, and selfie-retention tables created by the related modules

Important data rules:

- Do not recreate or reset the production database during an update.
- Apply only committed migrations through the supported deployment workflow.
- Make a verified backup before schema-affecting work.
- Keep employee data, photos, selfies, and database exports outside Git.

## Security design

- Owner-scoped database queries
- Admin platform authentication plus a separate administrator username/password layer
- PBKDF2-based administrator password hashing
- Salted employee PIN hashing
- Hashed admin and employee session tokens
- Login-attempt lockout and session expiry
- Same-origin checks on sensitive write routes
- R2 photo access validated against the authenticated owner and HR record
- Six-digit employee PINs are never returned after provisioning
- Android WebView blocks cleartext traffic, mixed content, file access, and external navigation
- No signing key, bridge secret, admin token, or production password is stored in this repository

Selfies and device-reported GPS are attendance evidence. They are not face-recognition, liveness verification, or protection against GPS spoofing.

## Validation and tests

Run static checks:

```bash
pnpm exec tsc --noEmit
pnpm lint
```

Run the available automated checks:

```bash
for check in checks/*.mjs; do node "$check"; done
```

The checks cover core calculations, API behaviour, save guards, employee onboarding, attendance, mobile security, payroll rules, loans, final settlements, notifications, deletion, record synchronisation, data quality, document renewals, backup logic, and selfie retention.

Real-device testing is still required for Android installation, camera access, GPS accuracy, WebView behaviour, notification permissions, and network conditions.

## Android application

The Android application is a restricted WebView wrapper for the employee attendance portal.

- Package: `net.greenmile.attendance`
- Minimum Android version: Android 8 / API 26
- Target SDK: API 35
- Camera: fresh selfie capture
- Location: attendance policy and optional geofence
- No microphone, contacts, SMS, background-location, or storage permission
- No admin token or attendance bridge secret embedded in the APK

Build environment variables:

```text
GREEN_MILE_ANDROID_SDK
GREEN_MILE_SIGNING_KEY
GREEN_MILE_KEY_PASSWORD
GREEN_MILE_ECJ_JAR        # optional compiler fallback
```

Build:

```bash
cd android-app
bash build.sh
```

Preserve the original signing key. Android will not install a future update over the existing app if it is signed with a different key.

## Deployment

Production is deployed as a private Cloudflare-hosted Site.

Recommended update flow:

1. Create a backup and confirm the target database.
2. Make changes on a separate branch.
3. Run TypeScript, lint, business-rule checks, and a production build.
4. Review database migrations and confirm they preserve existing data.
5. Test desktop and mobile interfaces.
6. Merge the reviewed change.
7. Deploy through the approved Sites/Cloudflare workflow.
8. Verify login, records, attendance, reports, storage, and mobile access after deployment.

Pushing code to GitHub does **not** automatically change the live software unless a deployment workflow is explicitly configured and run.

## Operational limitations

- Hardware fingerprint/face-attendance integration requires the actual device vendor API and on-site testing.
- Mobile selfie capture is not biometric face recognition.
- GPS is device reported and may be spoofed.
- Payroll output must be reviewed by HR before approval or payment.
- Payroll export is not a bank-validated UAE WPS/SIF submission.
- End-of-service calculations are guidance and require policy/legal review for the employee's circumstances.
- Large workspaces require server pagination beyond the current application limits.
- Production secrets, employee documents, and R2 image bytes are not included in source-code backups.

## Backup and recovery

- Use the application's JSON backup before material data changes or deletion.
- A GitHub repository is a source-code backup, not a production database backup.
- R2 photographs/selfies require a separate authorised storage-backup process.
- Test restoration procedures before relying on them for disaster recovery.

## Ownership and confidentiality

This software and repository are intended for authorised Green Mile Recycling LLC use. Repository access must remain private and limited to approved maintainers.

---

Prepared for **Green Mile Recycling LLC**

Project owner: **Faheem Shahzad**
