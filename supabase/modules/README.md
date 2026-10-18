# Administrative modules and browser-session security

Applied to the existing Supabase project, in this order:
1. admin_modules.sql
2. admin_grants.sql
3. admin_device_security.sql
4. business_security.sql
5. security_indexes.sql

catalog_seed.sql seeds the approved service catalog (no generated IDs are hardcoded). test_admin_security.sql runs transactional fixtures and rolls them back.

## Access
All exposed tables have RLS and explicit column grants. No secret/service-role key is shipped. Administrative permissions require a confirmed account, an active private role, an AAL2 JWT, a live Auth session and a nonrevoked browser-session registration. Registrations expire in 30 days. A browser UUID/label identifies a session for display; it is not an authentication credential. TOTP is the proof of possession.

The first administrator must finish TOTP enrollment in the app. Save the authenticator key securely. The implementation does not enroll or generate an administrator's factor on their behalf. Losing all authenticators requires recovery through the Supabase project owner. Revoking a browser registration blocks administrative data operations even while its access token remains unexpired. Role changes take effect at database permission checks.

Only the principal can manage staff roles. Principal role cannot be modified by the staff function. Roles: moderator (applications/catalog/promotions/verifications/audit), support (clients/tickets), finance (ledger/statements).

## Modules
- Append-only manual cash ledger in integer cents, idempotent request UUID, approved-business activation snapshot, monthly statements and CSV/PDF UI. No automatic billing, banking connection or money movement.
- Promotions: draft/published/paused, language and schedule, approved businesses only. Public API exposes only currently published promotions.
- Support: account-owned tickets and replies; support staff can change status and reply.
- Verifications: manual commercial register/license/insurance consultation records, public references and expiration dates. No identity-document collection.
- Catalog: add or deactivate approved family/service entries. User proposals remain in applications until reviewed.
- Settings: public support email and notice; principal can write.
- Audit records: staff changes, sessions, ledger, promotions, ticket status, catalog, settings, verifications.

## Verification
Transactional database checks cover AAL1 rejection, unregistered sessions, verified-session permission, role escalation, principal protection, cross-account tickets, self-approval rejection, disallowed sensitive fields, approved publication, ledger snapshot, public promotions, revocation and anonymous denial.
DOM-emulation checks cover forms, login, menus and MFA challenge. Integer-cent monthly arithmetic has a standalone Node test. Actual authenticator enrollment and real-device visual verification require the owner.
Supabase advisors: leaked-password protection remains disabled in project Auth settings; enable through the dashboard if supported by the plan. No callable configuration tool was available. Recovery-email redirects/SMTP still need end-to-end delivery verification.
Global translation, GPS radius, file uploads and confirmed-service reviews are outside this administrative migration.
