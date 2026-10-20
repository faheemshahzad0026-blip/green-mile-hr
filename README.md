# Green Mile HR — UAE workspace

A private web HR application for PC and mobile browsers, backed by Cloudflare D1 and Sites authentication. The first delivered build supports central employee records, department records, shifts, attendance, leave decisions, monthly payroll drafts, adjustment tracking, document expiry metadata, recruitment, assets, performance, disciplinary records, device registration, gratuity estimates, reports and JSON backup export.

## Use
1. Open the private deployment and sign in with the owner's ChatGPT account.
2. Add company details, departments, employees and shifts, in that order.
3. Record attendance manually or import up to 500 CSV rows per import. Use the template available on Attendance. Dates in CSV are YYYY-MM-DD, displayed as DD/MM/YYYY. Use the generated employee code, not the database row ID.
4. Generate payroll drafts for a month. Review salary proration, attendance, leave, overtime, loans and deductions manually. Approve and mark paid only after payment; payment date is required.
5. Open View to print one record or one salary slip. Use Print / PDF to save a PDF from your browser; Excel exports produce .xlsx files with the supplied company logo.
6. Download a JSON backup before deleting records.

## Hardware attendance
The Face & fingerprint module registers device details. No hardware connector is implemented because no machine/model is available. CSV imports retain their stated method but do not prove biometric identity. An actual integration needs the vendor API/protocol, employee device-ID mapping, timezone handling, a secure on-premises bridge for private-network devices, event deduplication and hardware testing. Raw biometric images/templates are not collected.

## Scope and operational limits
- This is an initial working HR application, not a completed enterprise HR platform or a Windows EXE.
- Deployment is owner-private. Employee self-service, shared company memberships and granular admin/HR/employee roles are not implemented.
- Payroll generation creates drafts from employee salaries. It does not auto-apply adjustments, proration, statutory leave accrual, sick/maternity pay, pension or loan recovery. Adjustments are a separate tracking register.
- Exported payroll CSV is not a validated WPS/SIF bank file and no MOHRE submission is performed.
- End-of-service is a guidance estimate for eligible expatriate full-time employees under federal private-sector rules. It excludes DIFC/ADGM, pension, alternative savings schemes and complete final settlement.
- Document records store metadata, not file attachments. PDF export uses browser printing, Excel exports use .xlsx with an embedded company logo. JSON backup export has no automatic restore.
- Lists are paginated on the client (25 rows/page); the current load limit is 10,000 workspace records. Server pagination is required before exceeding that limit.
- Audit export includes the latest 100 events. Full audit history remains in the database.
- Employee codes are immutable generated numbers based on database IDs; gaps can occur.
- Overnight attendance must be split into separate daily records.

## Development
Node 22+, pnpm. Run the Sites install helper, `pnpm exec tsc --noEmit`, `node checks/calculations.mjs`, `node checks/api.mjs`, and the Sites build helper. Apply committed D1 migrations through the supported Sites deployment workflow. Do not recreate or reset the database during updates.

## UAE references reviewed 08/10/2026
- https://u.ae/en/information-and-services/jobs/Sector-of-employment/employment-in-the-private-sector/Types-of-leaves
- https://dda.gov.ae/en/gratuity-calculator/gratuity-calculator
- https://www.mohre.gov.ae/en/guidance-and-awareness-portal-new/wages-protection-system

Company-specific payroll and leave policy must be confirmed before operational payroll use.

## Validation
TypeScript checks, production build, payroll/gratuity boundary checks and SQLite migration/uniqueness/owner query checks passed. The branding update includes the supplied transparent PNG, higher contrast green surfaces and Escape handling for forms, mobile navigation, pages and print windows. No browser UI QA or real hardware test was performed in this environment.

## Keyboard controls
Press Escape to close the open record form, details or deletion dialog. With no dialog open, Escape closes the mobile menu first, otherwise returns the current page to Overview. Unsaved form edits are discarded when Escape closes the form.

## Mobile attendance & save improvements
The Mobile attendance screen records administrator-entered check-in/out against an employee. Time is assigned server-side in Asia/Dubai; duplicate punches and checkout before check-in are rejected. Company settings can require GPS, allow optional location, or enforce an office geofence. GPS is device-reported and can be spoofed; it does not prove identity or substitute for a biometric device. A geofence requires valid latitude, longitude and a positive radius, and conservatively includes reported GPS uncertainty. Overnight attendance requires a manual correction.

The private application remains owner-only. No staff self-service, staff login or employee invitations have been enabled. Staff access needs an explicit membership model and access setup before rollout.

PWA manifest and a network-only service worker are included. Open `/?view=mobile` from Chrome on Android or Safari on iPhone. Android can use Install app/Add to Home screen; iPhone can use Share > Add to Home Screen. Availability depends on browser/install criteria and the hosted sign-in boundary; actual device installation has not been tested. This is not an APK or App Store binary. Attendance requires internet. HR records and authenticated pages are never stored in a service-worker cache.

Create/update/delete/import/payroll writes now return the changed records, allowing the UI to update after server confirmation without a full workspace reload. Create and audit are in a single database batch. Audit data is fetched only when exporting backup. No measured live latency claim is made.

The employee form has aligned field labels and an always-visible Save/Cancel footer. Selected navigation and focused form fields have stronger borders and colour. Employee print profiles are grouped into personal, employment and salary/bank sections with a summary and larger screen typography.

Route integration tests on an in-memory SQLite database verify saved-record responses, mobile in/out, duplicates, location policies, metadata preservation, linked-delete protection, owner separation and missing-auth rejection. Phone, browser and GPS hardware tests remain outstanding.

## Detailed document expiry centre
Separate category tiles for Passport, Visa, Emirates ID, Labour card, Work permit, Insurance, Driving licence and Contract filter the existing records. Each category opens its own document form with shared dates and number plus relevant details: issuing country/authority, visa UID/sponsor/category/profession, Emirates card number, insurance provider/coverage, licence category, or contract type/employer. Optional reminder window and renewal application reference/date are stored per document. No file upload is implemented.

The table includes employee, document type/number, issue date, expiry date, days remaining/overdue and a date-derived expiry state. Expiry state is calculated for Dubai's current date; it does not rewrite stored records. Filters cover employee, expired, today and the next 7/30/90 days. Type tiles, summary counts, views and PDF/Excel exports reuse the same saved records. Renewal pending is a workflow state and can overlap an expired document. Tests cover expiry boundaries and preservation of type-specific details. Fonts, input borders and action buttons were enlarged.

## Employee Android app, PIN access & selfie evidence
The signed APK is available in Employee app access and as public/Green_Mile_Attendance.apk. This is an Android WebView client for a separate employee-only gateway. The admin Site remains owner-private. The gateway login page is accessible to employees; credentials and attendance remain protected by a six-digit PIN and opaque session. Each employee account is linked to an existing employee record and can be enabled, reset, disabled or removed without deleting attendance. Password/PIN hashes, lockouts and session tokens are not exposed in list responses. PIN reset/revocation clears all associated sessions.

Selfies are captured as JPEG in the employee UI, limited to 600 KB and stored in R2 with an ownership key. Time is assigned server-side; submitted GPS is checked against company policy. Employee-punch requests cannot select a different employee from the logged-in identity. Admin Attendance > View displays check-in/out selfies and map links. Selfie URLs require admin sign-in and ownership validation. The APK and browser never receive the private admin service credentials. The gateway's server uses ADMIN_SITE_ACCESS_TOKEN and ATTENDANCE_BRIDGE_SECRET, stored as runtime secrets.

Schema changes only add mobile_accounts/mobile_sessions, preserving all existing tables and data. A pre-change snapshot of hr_records and hr_audit was taken. JSON HR backup does not include R2 selfie bytes or mobile secrets. Selfies/GPS are evidence, not identity/liveness verification or protection from device spoofing. Retention/cleanup automation and bulk photo backup are not yet implemented.

PIN/security tests verify hashing, attempt lockout, session hashing, bridge-secret checks, employee isolation, selfie/GPS requirements, duplicate punches, protected photos and revocation. Android APK signing/package checks pass; real phone camera/GPS/install testing remains outstanding.
