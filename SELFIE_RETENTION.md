# Attendance photo retention

User requested deleting attendance selfies after each month while keeping attendance and payroll.

This Site is owner-private (project appgprj_6ac7cc236658819181e038b1d95b1e6b). The unattended writer is POST /api/selfie-retention with JSON {"action":"monthlySelfieCleanup"}. Obtain fresh service access from Sites get_site and send its bearer only in OAI-Sites-Authorization to the exact Site URL. Do not forward or spoof visitor identity headers. Do not expose or persist the bearer. Before changing the Site's audience or migrating hosting, replace reliance on the private Site boundary with explicit service authentication and configure a server cron job.

The writer's owner is fixed in lib/selfie-retention.ts from the workspace records. Callers cannot supply owners, object keys, date cutoffs or prefixes. The server calculates the first day of the current month at midnight Asia/Dubai and deletes only earlier-uploaded objects below this owner's selfies/ prefix. profiles/ and documents are excluded. Actual upload time, not attendance date, handles overnight shifts crossing the month boundary.

Run on the first day of each month at 00:15 Dubai time. Repeat POST until hasMore=false. A busy result means another runner holds a two-minute lease; retry on a later task attempt. Error or unfinished batches must be reported, not claimed complete. Cursor progress and a persistent deletion queue make reruns safe. R2 deletes happen before removing only selfie references from attendance JSON. Attendance, time, GPS, payroll and profile photos are never deleted. Existing JSON backups may retain obsolete photo keys but contain no image bytes. Deletion of expired images is permanent.

Verification: exercise the same service endpoint after publication, follow bounded batches and confirm the returned cutoff/counts. Only expired photos can be deleted by verification; current-month photos remain untouched.
