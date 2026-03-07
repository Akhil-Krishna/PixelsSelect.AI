

HiRe.AI — product name.
 
 
---
 
# HiRe.AI — Product specification and implementation brief
 
## Overview
 
HiRe.AI is an enterprise-ready AI-powered hiring and interview platform. It enables organizations to register and manage users (Admin, HR, Interviewer/Employee, Candidate), schedule interviews, run AI-driven or hybrid interviews (AI + human), record sessions, evaluate candidates across voice/vision/code channels, and generate reports. This spec describes the corrected and production-ready feature set, architecture, security rules, UI expectations, and acceptance criteria.
 
## Primary goals
 
1. Secure WebRTC access and signaling.

2. Correct organization-scoped access and multi-tenancy.

3. Strict role-based permissions.

4. Consistent interview scheduling and visibility across dashboards.

5. Production-ready real-time infrastructure (TURN, Redis, Celery).

6. Teams-style meeting UI for interviews.

7. Full recording, reporting, and auditability.

8. Replaceable AI microservices (pluggable components).
 
---
 
## Tech stack (recommended)
 
* Backend: FastAPI (async) — Python 3.11.9 

* Frontend: Next.js (React)

* Real-time: WebSockets (FastAPI) and WebRTC (browser)

* DB: PostgreSQL (primary)

* Cache / pubsub: Redis

* Async tasks: Celery (free Redis broker) 

* Object storage: S3-compatible (AWS S3, MinIO) or any must fallback if any issue gracefully 

* Optional search: OpenSearch for indexing question banks / resumes

* Models: self-hosted open-source models (Whisper, DeepFace, Mistral, code-eval model). All AI components run as replaceable microservices.

* CI/CD, monitoring, secrets: GitHub Actions, Prometheus/Grafana, Sentry, Vault/Secrets Manager

* Container orchestration: Docker + Kubernetes (Helm charts)
 
---
 
## Roles and permissions (RBAC)
 
* **ADMIN** — full access to the organization: create users, manage billing, see all org interviews and reports.

* **HR** — schedule interviews, upload question banks, invite interviewers, view org interviews and reports.

* **INTERVIEWER** — assigned by HR, can observe/join assigned interviews, ask questions, annotate results.

* **CANDIDATE** — can attend assigned interviews, complete verification steps, view their basic result summary.
 
**Key permission rules**
 
* Admins: access across org.

* HR: can see only interviews belonging to their organisation (not other orgs).

* Interviewers: can view/watch only interviews they are assigned to.

* Candidates: can only access their own interviews.

* Guest join via one-time code is allowed only for the candidate (or invited guest) and constrained by time windows.
 
---
 
## Authentication & registration (You can read this and if issues come up with a better plan for auth )
 
* Organization registration flow:
 
  * Org Admin registers the organization.

  * Admin provisions HR and Interviewer accounts for the organisation or allows HR to add them.

* Self-registration:
 
  * For security, permanent HR and Interviewer accounts must be created by org Admin or via an admin approval endpoint. Public open registration should **default to CANDIDATE** role only.

* Candidate onboarding:
 
  * When HR schedules an interview, generate a demo password or one-time link and email just about the interview right away then just 5 minutes before actual interview time email with interview link to the candidate mail. 

  * Optionally require candidate to complete ID upload and live face capture before joining (see Verification).

* Token: JWT access tokens with short lifetime and refresh tokens; include user id, role, and organisation_id claims. Sign and validate tokens server-side.
 
---
 
## Verification (optional but recommended)
 
* Candidate verification flow:
 
  * Upload government ID (stored encrypted in S3/for dev gracefully fallback to normal storage or you decide ; minimal PII in DB — store hash/reference). 

  * Live capture via webcam (one or more photos or short video).

  * Backend face verification service compares live capture vs ID photo using DeepFace/OpenCV.

  * Liveness checks (blink detection, motion prompt) to reduce spoofing risk.

* Secure storage: encrypt ID files at rest; apply RBAC so only authorized org Admin/HR can access raw files (avoid exposing in UI).
 
---
 
## Interview scheduling & integrity rules
 
* HR schedules interview with:
 
  * job role, title, candidate email, date/time, duration, description, question bank, resume file upload, and assigned interviewers. 

* Validation on scheduling:
 
  * Interviewers added must belong to the same organisation as the HR (organisation_id equality).

  * Interviewers’ email domains must match the organisation domain when domain policy is required.

  * Candidate email may be external; a guest token or account is created for them.

* Time-window rules:
 
  * Candidates can join only at scheduled time or within a configured window (e.g., from scheduled time up to +10 minutes), not before.

* Notifications:
 
  * Immediate email on scheduling(without link) and a reminder email 5 minutes before the interview with actual interview link. 

  * Use Celery for asynchronous email sending; support SES/SendGrid/Mailgun.
 
---
 
## Dashboards and visibility requirements
 
* Admin dashboard: all org interviews and reports.

* HR dashboard: all interviews for the HR’s organisation (not just those created by that HR).

* Interviewer dashboard: only interviews where the interviewer is assigned.

* Candidate dashboard: only the candidate’s interviews.

* All lists must be explicitly ordered by scheduled time (e.g., `scheduled_at ASC` for upcoming interviews). Pagination and filtering supported.
 
---
 
## WebRTC & WebSocket signaling security (critical)(you can decide and come up with better plan)
 
**WebSocket endpoint**: `app/api/v1/endpoints/webrtc.py` (or similar).
 
**Requirements**
 
1. Do not accept or join rooms until the user is authenticated and authorized for that specific interview.

2. Accept JWT via header or `?token=` on WebSocket handshake, decode and validate signature and expiry.

3. After decoding the token, **load the interview record by its access token or interview id** and then load the user record from DB.

4. Enforce the following authorization logic **before** establishing any signaling or adding to room state:
 
   * If role == `CANDIDATE`: allow only if `user.id == interview.candidate_id` OR `user.role == ADMIN`.

   * If role == `WATCHER` (HR/INTERVIEWER):
 
     * `ADMIN`: allow always.

     * `HR`: allow only if `user.organisation_id == interview.hr.organisation_id`.

     * `INTERVIEWER`: allow only if there is an `InterviewInterviewer` assignment linking that user to the interview.

   * Otherwise close the WebSocket with an appropriate error code (e.g., 4003 Forbidden).

5. If the interview is not found, close with 4004 Not Found.

6. Keep WebSocket handlers fully async and do not perform blocking DB calls. Use async SQLAlchemy sessions.
 
---
 
## Multi-worker scaling for signaling
 
* In-memory `rooms` state is acceptable for single-worker dev systems only.

* For production or multi-worker deployment:
 
  * Use Redis as shared room registry and Redis pub/sub to forward signaling messages between processes.

  * If Redis is not configured, fall back to in-memory rooms **and** produce a warning in logs and docs explaining single-worker limitation.

  * Do not crash if Redis is absent; degrade gracefully.
 
---
 
## TURN/STUN and NAT traversal
 
* Client-side RTC configuration must include:
 
  * Public STUN servers (fallback)

  * A TURN server configuration for reliable connectivity behind symmetric NAT/firewalls (auth required).

* Make TURN URLs and credentials configurable via environment variables.
 
---
 
## Recording and storage
 
* Automatic recording requirement:
 
  * Record candidate video + audio and any streams that are necessary for auditing.

  * Approaches:
 
    * Client-side recording (RecordRTC) that uploads blobs to backend on session end, OR

    * Server-side recording using a media server (e.g., Janus/mediasoup) for higher fidelity and scalability.

  * Store recordings in S3 with encryption at rest and lifecycle policies.

  * Recordings are linked to interview record and report.

  * Access restrictions: HR/Interviewer/Admin (org-scoped) can access recordings. Candidate can see status (available) but not necessarily raw recordings (policy configurable).

  * Support redaction and retention policies (e.g., auto-delete after N days).
 
---
 
## AI microservices & pluggability
 
* All AI capabilities should be implemented as loosely coupled microservices:
 
  * STT service (Whisper or replacement)

  * TTS service

  * Vision / face analytics (DeepFace/OpenCV)

  * LLM service for dialog (Mistral or equivalent)

  * Code evaluation service (DeepSeek-Coder or groq / code-eval model)

or  u can use same groq model for Q&A and code evaluation 

* Provide a configuration layer to switch implementations without code changes (via DI or environment config).

* Run heavy AI inference on dedicated GPU nodes or a separate inference service.
 
---
 
## Interview UI — Microsoft Teams style (detailed)
 
**Goal:** interview room UI should resemble a modern meeting interface similar to Microsoft Teams.

Real-time analytics: confidence score, emotion summary, integrity flags (multiple faces, gaze, tab switches)
 
 
**Layout **
 
* **Left panel (narrow)**: meeting metadata and monitoring widgets:
 
  * Meeting details, schedule, job role

  * Real-time analytics: confidence score, emotion summary, integrity flags (multiple faces, gaze, tab switches) for interviewer/hr (watchers) for candidate left panel can be simply alerts with extra something as you like just in like Microsoft teams

  * Small controls: meeting settings, participant list summary

* **Center (main)**: video grid / primary speaker view:
 
  * Primary candidate tile large and centered by default.

  * Other participants (AI, HR/interviewer) shown as tiles.

  * When multiple people are present, show a grid with a pinned speaker.

  * Each video tile shows name, role, and speaker indicator; AI tile shows an AI logo and color accent when speaking.

* **Right panel (chat + code editor)**:
 
  * Tabbed right panel: Chat (timestamped messages), Code Editor), Notes/Annotations.

  * Chat messages show sender role and are recorded in session logs.

  * Code editor: Editor (code mirror / or monocco or ace or any better easy set up and better one) with on-change streaming via WebSocket; code submissions are evaluated and results appended to chat or a results pane. 

* **Controls**:
 
  * Mute/unmute, toggle camera, share screen(while starting meeting only scrren will be shared by the candidate), raise hand, end call.

  * HR/interviewer can pause the AI agent and ask direct questions; AI resumes when HR allows.

* **Responsiveness**: layout adapts to mobile/smaller screens (e.g., stacked panels).

* **UX**: friendly, accessible, minimal visual clutter, consistent colors and spacing.
 
---
 
## Reports & post-processing
 
* A Celery job compiles a JSON report after interview ends:
 
  * Q&A relevance scores

  * Code evaluation (logic/syntax/auto-tests)

  * Vision metrics (confidence, emotions aggregated)

  * Integrity metrics (faces count, tab switches, suspected cheating)

  * Final recommendation and pass/fail threshold

* Store report in DB and optionally generate a PDF for HR.

* Email report to HR and interviewers; candidate sees a summary (pass/fail and brief strengths/weaknesses) but not sensitive details or raw recordings.
 
---
 
## Data privacy & compliance
 
* Encrypt PII and recordings at rest.

* Access control for sensitive assets.

* Data retention policy with configurable TTLs.

* Audit logs for changes and access to recordings and reports.

* Support export/deletion requests for GDPR compliance.
 
---
 
## Database & API design notes (high level)
 
* Core tables: `organizations`, `users`, `roles`, `interviews`, `interview_interviewers`, `question_banks`, `recordings`, `reports`, `ai_events`, `audit_logs`.

* Indexes on `interviews.scheduled_at`, `interviews.organization_id`, `users.email`.

* Use `selectinload` or proper ORM eager loading for dashboards to avoid N+1 queries.

* Always filter by `organization_id` for org-scoped endpoints.
 
---
 
## Acceptance tests (minimum)
 
1. **WebRTC ACL test**
 
   * Candidate token for an unrelated candidate cannot join other candidate’s interview.

   * Interviewer token for unrelated organisation cannot watch interview.

   * HR in the same org can watch interview.

2. **HR visibility test**
 
   * HR user sees interviews for their organisation (created by any HR in that org).

3. **Scheduling test**
 
   * Interview created appears on candidate, HR, interviewer dashboards.

   * Reminder email triggered 5 minutes before.

4. **Join time-window test**
 
   * Candidate cannot join earlier than window; can join at scheduled time or within allowed late window.

5. **TURN test**
 
   * P2P works in restricted network environments when TURN configured.

6. **Recording test**
 
   * Recording is generated, uploaded, and accessible only to authorized org users.

7. **Fallback behavior**
 
   * If Redis not available, system logs warning and remains functional in single-worker mode.
 
---
 
## Deliverables required from the implementer
 
1. Updated codebase (ZIP) containing:
 
   

   * Infrastructure: example `docker-compose.yml` for local dev including Redis, Postgres, and Celery.

   * Tests: automated tests for core acceptance cases (pytest).

2. A clear change list showing which files were modified, added, or deleted.

3. Documentation:
 
   * Setup instructions (local and production).

   * Configuration options (TURN servers, Redis, S3, AI endpoints).

   * Security notes and privacy/retention settings.

4. Migration scripts (if DB schema changes).

5. A short demo checklist to run the app locally and verify core flows.
 
---
 
## Additional engineering constraints and best practices
 
* Maintain fully asynchronous code paths; avoid blocking calls in request handlers and WebSocket handlers.

* Keep AI components as replaceable microservices; use interface/adapter patterns.

* Use environment variables for secrets and configuration (12-factor).

* Provide sensible defaults for dev (local STUN servers, in-memory fallback).

* Use centralized logging and error reporting.

* Document single-worker limitations for signaling if Redis is not provided.
 
---
 
## Final review
 
Implement HiRe.AI, an enterprise AI-powered hiring platform. Key goals: secure WebRTC + signaling; strict RBAC and multi-tenant org isolation; Teams-like interview UI; automatic recording and reporting; pluggable AI microservices; production-ready infra (TURN, Redis, Celery, S3).
 
Must-haves:

- Backend: FastAPI async.

- Frontend: Next.js with any best Editor.

- DB: PostgreSQL.

- Cache/pubsub: Redis (fallback to in-memory with warning).

- Async tasks: Celery.

- Recording: client-side or media-server; store in S3 with encryption.

- AI: separate microservices for STT, TTS, vision (DeepFace/OpenCV), LLM dialog, and code-eval. Make these pluggable via config.
 
Security & behavior rules (strict):

1. JWT auth with user id, role, organization_id claims.

2. WebSocket signaling MUST authenticate token, load interview record, and authorize the user for that interview BEFORE joining rooms. If not authorized, close the socket (4003 or 4004).

3. HR sees all interviews for their organization (join Interview.hr, filter by organisation_id).

4. Interviewers can only watch interviews they are assigned to (InterviewInterviewer join).

5. Enforce same-organisation and same-email-domain for interviewers when HR schedules interviews. Return HTTP 400 on violation.

6. Candidate self-registration: default to CANDIDATE role. Only Admin can create HR/INTERVIEWER (or use an admin approval flow).

7. Lists must be ordered by scheduled_at ASC.

8. Use Redis for shared room state & signaling in multi-worker deployments; fall back to in-memory with clear log message if Redis is absent.

9. TURN server config must be supported via env variables for reliable WebRTC.
 
UI requirements:

- Interview room like Microsoft Teams:

  - Left panel: meeting details and monitoring (confidence, integrity flags) for interviewer and hr , for candidate just provide alert there.

  - Center: main video grid with primary candidate tile; AI has a tile with logo and speaker indicator.

  - Right: chat ( editor open when coding question is asked by the AI) 

  - Controls: mute/camera/screen-share/pause AI/end call.

  - Responsive layout, accessible styling.
 
Acceptance tests (must pass):

- WebRTC ACL enforcement for candidate/interviewer/hr/admin.

- HR visibility across organisation.

- Scheduling validation (interviewer org/domain check).

- Reminder email 5 minutes prior.

- Recording upload and RBAC.

- Redis fallback behavior.
 
TechCorp — example customer.

Kakkanad — example location.

Bheem - admin of techcorp

Priya — example HR user of techcorp. 

Arjun — example candidate.

Raj — example interviewer of techcorp.
 
must provide demo in db for testing
 
Follow best practices (async code, no blocking DB calls, DI-friendly microservices, use environment config for secrets). Provide documentation and migration scripts if DB changes are required.
 
 
 