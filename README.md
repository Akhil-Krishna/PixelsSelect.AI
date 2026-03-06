# HirE.AI / Pixel-Select — Intelligent Interview Platform v2.0

AI-powered interview platform with real-time monitoring, speech recognition optimized for Indian English, live interviewer controls, recording, resume integration, and organisational RBAC.

---

##  Quick Start (5 minutes)

### Prerequisites
- Python 3.11.9 or +
- A free Groq API key: https://console.groq.com

### Setup

```bash
# 1. Clone / unzip the project

cd pixelcore
# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env .env.local    # Edit .env and set your GROQ_API_KEY
# Minimum required: GROQ_API_KEY=gsk_...

#5. Run the celery worker 
celery -A app.core.celery_app:celery_app worker --loglevel=info

# 6. Run
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000

---

## Demo Accounts

| Email | Password | Role |
|-------|----------|------|
| admin@demo.com | admin123 | Admin |
| hr@demo.com | hr123456 | HR Manager |
| interviewer@demo.com | int12345 | Interviewer |
| candidate@demo.com | can12345 | Candidate |

All accounts belong to **Demo Corp** organisation.

---

## Organisational Structure

```
Organisation (e.g. "Acme Corp")
├── Admin        — full access, user management
├── HR Manager   — schedule interviews, see results, upload resumes
│   └── can only assign Interviewers from SAME org
├── Interviewer  — join live, pause AI, ask manual questions, see results
└── Candidate    — join interview via unique link, no metrics shown
```

---

## Features

### Interview Room (Candidate)
- **Voice-to-text** with Indian English support (`lang='en-IN'`) using Web Speech API
- **Code editor** with syntax highlighting — auto-opens for coding questions
- **Screen + webcam recording** — composite (screen + cam inset)
- **Tab switch detection** — flags raised instantly on tab change
- **Face monitoring** — flags for looking away, multiple faces
- **Alerts panel** — candidate sees integrity flags only (not confidence scores)

### Live Monitor (Interviewer / HR)
- **Real-time message polling** — new messages appear every 2 seconds without refresh
- **Pause AI** — take over and ask manual questions directly
- **Resume AI** — hand back control to the AI
- **Live metrics** — tab switches, message counts, session duration
- **Recording playback** — after interview ends

### Dashboard
- **Admin**: User management, all interviews, org management
- **HR**: Schedule, assign interviewers (same org only), upload resumes, see reports
- **Interviewer**: Assigned interviews, live watch, results
- **Candidate**: Upcoming interviews, join button, results

### AI Interviewer
- Uses Groq (free) / Ollama / OpenAI — configurable via `.env`
- **Question Bank**: HR uploads questions; AI uses them in order
- **Resume context**: AI tailors questions based on candidate's resume
- Fallback to scripted responses if API unavailable

---

## Configuration

```env
# .env

# LLM Provider (pick one)
LLM_PROVIDER=groq          # groq | ollama | openai | mock
GROQ_API_KEY=gsk_...       # Free: https://console.groq.com
GROQ_MODEL=llama-3.3-70b-versatile

# For local Ollama:
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.2

# Vision (face analysis)
VISION_PROVIDER=deepface       # mock (no deps) | deepface (needs TF)

# Email
EMAIL_PROVIDER=log         # log (console) | smtp (real Gmail)
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # Gmail App Password
```

---



## How to run an Interview

1. **HR logs in** → Schedules an interview
   - Enters candidate email (auto-creates candidate account + sends invite)
   - Optionally: uploads question bank (one per line or JSON)
   - Optionally: uploads candidate resume (PDF/TXT)
   - Assigns interviewers from org's interviewer pool

2. **Candidate** receives email with unique interview link --- issue fix needed

3. **Candidate joins** → Camera/mic check → Interview starts
   - AI conducts interview using question bank + resume context
   - Code editor for coding questions
   - Voice input with Indian English accent support

4. **Interviewer** can open `/watch/<token>` (or click Watch in dashboard)
   - Sees live messages auto-updating
   - Can pause AI and take over with manual questions
   - Resume AI when done

5. **Interview completes** → Scores calculated → Report visible in dashboard


---

## Indian English Speech Recognition

The platform uses the Web Speech API with `lang='en-IN'` which is supported by:
- Chrome (best support)
- Edge
- Safari (limited)

This handles Indian English accent patterns natively. No server-side STT needed — it runs entirely in the browser, zero latency.

For even better accuracy with Indian accents, you can integrate:
- **Whisper.cpp** (local, free) — run as a sidecar service
- **Sarvam AI** (Indian language specialist, free tier)

- **whisper with fine tuned on indian eng**

---

## Scaling

- Switch to PostgreSQL for production
- Add Redis for session caching
- Deploy behind Nginx for HTTPS + load balancing
- Add Celery for async email/report generation

## Note

Vision Service — Real-time Emotion Analysis + Cheating Detection
================================================================
Provider: DeepFace + OpenCV Haar cascades.

VISION_PROVIDER=deepface  → real ML analysis (TensorFlow, ~1.5GB auto-download)
VISION_PROVIDER=mock      → scripted scores, no ML deps needed

THREE CRITICAL PRODUCTION FIXES APPLIED IN THIS VERSION:

1. THREAD POOL OFFLOAD
   DeepFace.analyze() and all OpenCV work run in asyncio's default thread pool
   via loop.run_in_executor(). Without this, a 300ms DeepFace call blocks the
   entire event loop, freezing all other requests (chat, vision, API) for that
   duration. Fixed: _run_vision_sync() contains all blocking work; async wrapper
   calls it via run_in_executor.

2. CACHED HAAR CASCADE
   The original code called CascadeClassifier() on every frame — this reloads
   the XML file from disk each time (~5-10ms I/O per frame). Fixed: the cascade
   is loaded once at module level and reused for all frames.

3. SUCCESS FLAG ACCURACY
   The original set result["success"] = True unconditionally at the end of
   _analyze_deepface(), even if DeepFace threw an exception and result["error"]
   was set. Fixed: success is True only if the emotion block completed without
   error, so the frontend can correctly detect degraded analysis.

# Context

## PixelsSelect.AI: AI-Powered Hiring and Interview Platform
## Overview
HirE.AI is an enterprise-ready web application designed to streamline the employee hiring process using AI agents for conducting interviews. The core idea is to create a platform where organizations can register, manage users (with roles like Admin, HR, and Interviewer/Employee), schedule interviews, conduct AI-driven or hybrid (AI + human) interviews, and generate comprehensive reports based on candidate performance.
The original user idea focused on a hiring app with AI interviewers handling voice Q&A, live coding evaluation, vision-based emotion/confidence analysis, cheating detection, and report generation. It included organizational dashboards for scheduling, email notifications with links, and scalability with replaceable AI models.
### Refinements and Add-Ons for Practicality
To make this implementable and production-ready, I refined the architecture based on best practices:
- **Multi-Role Support**: Added distinct roles (Admin for org management, HR for scheduling, Interviewer/Employee for observing/joining interviews). Candidates have separate logins with enhanced auth (e.g., optional ID proof upload and face verification using open-source libs like OpenCV for liveness detection).
- **Question Bank and Resume Integration**: HR/Interviewers can upload or define a question bank (stored in DB) and Resume of that candidate for AI to use during interviews. Fallback to AI's general knowledge if no bank is provided.
- **Hybrid Interviews**: Toggle between full AI mode and human-assisted (e.g., Interviewer joins via WebRTC). That is HR while scheduling can add interviewers to the meeting which are employees of that organisation who are registered as interviewers from that organisation 
- **Enhanced Dashboards**:
  - Org dashboards: Role-specific views (e.g., Admin sees user management, HR sees scheduling, Interviewer sees ongoing interviews).
  - Candidate dashboard: View scheduled interviews, with extra auth steps (e.g., face scan for verification before joining).
- **Security and Auth Enhancements**: JWT-based auth, role-based access control (RBAC), and optional biometric/ID verification to prevent fraud.
- **Real-Time Features**: WebSockets for live code sharing, WebRTC for video/audio (with emotion analysis on frames).
Code editor side by side , where users type in code and click send and lively appears to ai and evaluate and respond according to evaluated result , and then code which are send must be deleted from the editor using next js frontend capability or fast api
like more coding questions can arrive 

- **Report Generation**: Aggregates scores from voice (Q&A accuracy), vision (confidence/emotion/cheating), and code (logic/syntax). Stored in DB, emailed, and viewable in dashboards and download as pdf
- **Scalability Add-Ons**: Microservices potential, async tasks via Celery, containerization with Docker/Kubernetes, and model replacement via config.
- **Practicality Fixes**: Handled latency in real-time AI (e.g., batch processing for vision), privacy (data anonymization), bias mitigation (diverse datasets), and edge cases (e.g., human fallback if AI fails).
- **Automatic Interview Recording**: Added automatic recording of all interviews (video/audio streams) for post-review, compliance, and auditing, with secure storage and access controls. It can be like screenrecording or live recording of the interview 
Either add scrrenrecording there itself we can see user's cam feed right? 
These add-ons ensure the app is realistic: MVP buildable in 3-6 months by a small team, scalable to 100+ concurrent interviews, and compliant with basics like GDPR (data encryption/deletion).
- **Indian English Accent**: candidate will be talking in indian english , so accent vice issue might arise , speech to text must be perfect for indian accent , you can go for any open source model for that
- **Tab Switching** : If candidate switches tab , flag must be raised

- During interview time must be shown in UI , end option , mute option etc , must be like Microsoft teams meeting 
- where interviewer and HR can see detailed matrixe abut confidence score and emotion from deepface , OpenCV integrity , tab switches , etc 
-candidate dont want to see these matrix

- **Authentication and Dashboard**: authentication and security must be there like production level , dashboards must be ux friendly , interviewer and HR from same organisation , like organisational login 

-**Dashboard**: Interviewer , HR and Admin can see results and recording , interviewer can enter an interview and stop AI and ask manual questions, , interviewer can see live interviews without refresing 


**Note**
Every interviews full details , including conversations and code and report and recording must be saved in db 
### Reasoning Behind Design
- **Tech Stack Choice**: FastAPI for backend (async, high-performance for real-time AI); Frontend currently provide html but it can be replaced by Next js in future. Python excels in AI integrations (Hugging Face), outperforming Node.js for compute-heavy tasks.

Frontend using Next Js with actual production ready structure
- **Open-Source AI**: Chose self-hosted models (no tokens/costs) for privacy/cost; replaceable to allow upgrades (e.g., switch Whisper to Vosk).
- **Security Focus**: Roles prevent unauthorized access (e.g., candidates can't schedule). Extra auth for candidates reduces cheating.
- **Scalability**: Async processing avoids blocking; queues for reports/emails. Production: Use cloud (AWS/GCP) for auto-scaling.

## User Story
In a real-world scenario, imagine TechCorp, a mid-sized software company in Kakkanad, Kerala, looking to hire a Python developer. The HR manager, Priya, logs into her organizational dashboard using her secure JWT-authenticated account. She uploads a custom question bank via a simple JSON/CSV import, including technical questions on algorithms and system design. Priya then schedules an interview by entering the candidate's email, Arjun, selecting a time slot, and attaching the question bank. The system generates a unique link and code, sending an email notification to Arjun with a reminder one hour before. Arjun, a candidate from nearby, registers on the platform or joins as a guest using the code. Before entering the interview room, he completes enhanced verification: uploading an ID proof and performing a live face scan via webcam, where the backend uses DeepFace and OpenCV to confirm liveness and match against the ID to prevent fraud. Once verified, Arjun enters the virtual interview room powered by WebRTC for video/audio and WebSockets for real-time interaction. The AI voice agent, using Whisper for speech-to-text and XTTS-v2 for text-to-speech, starts asking questions from the bank or generates follow-ups via Mistral-7B LLM based on Arjun's responses. Simultaneously, the vision agent analyzes webcam frames every 5 seconds with DeepFace to score confidence (e.g., based on neutral/happy expressions), detect cheating (e.g., multiple faces or gaze aversion), and monitor emotions. When a coding question arises, a live editor (Monaco Editor for syntax highlighting and real-time sharing) appears; Arjun types code, which streams to the backend where DeepSeek-Coder evaluates logic and syntax against the question, providing instant feedback. Meanwhile, an Interviewer from TechCorp, Raj, joins the room from his dashboard to observe silently or toggle to hybrid mode, intervening via voice if needed. After the 45-minute session, the system ends the meeting, and a Celery task aggregates data into a report: Q&A relevance score (85/100), code accuracy (92/100), confidence level (78/100 with no cheating detected), and an overall recommendation to "Proceed." The report is emailed to Priya and Raj, stored in PostgreSQL for dashboard viewing, and anonymized for privacy. Arjun sees a summary in his dashboard, allowing him to edit his profile or upload a resume for future opportunities. This process saves TechCorp time, reduces bias through AI objectivity, and scales as they grow, handling multiple interviews concurrently via cloud deployment.
## Features
HirE.AI offers the following key features, explained with implementation details:
1. **User Registration and Role-Based Authentication**
   - **Description**: Organizations register with Admins/HRs. Candidates register separately. Roles: Admin (manage users), HR (schedule interviews), Interviewer/Employee (observe/participate), Candidate (attend).
   - **Explanation**: Uses JWT for sessions. Extra auth for candidates: Upload ID proof (stored securely in DB/S3), face verification (live capture via webcam, matched against ID using DeepFace/OpenCV for liveness/emotion to detect deepfakes).
   - **Implementation**: FastAPI Users library handles auth. For face verification: Frontend captures image/video, sends to backend; AI service analyzes (add `face_verify` endpoint in `ai.py`).
   - **Production Integration**: Use OAuth2 (Google/Microsoft) for SSO. Store sensitive data encrypted (e.g., Fernet). Rate-limit logins with FastAPI middleware.
2. **Role-Specific Dashboards**
   - **Description**:
     - **Admin/HR Dashboard**: User management, schedule interviews, view reports, upload question banks (e.g., JSON/CSV of Q&A for specific roles like "Python Developer").
     - **Interviewer/Employee Dashboard**: View scheduled/ongoing interviews, join as observer (see AI-candidate interaction), toggle to human mode.
     - **Candidate Dashboard**: View scheduled interviews, complete verification (ID/face), join meetings. Add simple features like profile editing, resume upload (without complexity).
   - **Explanation**: Dashboards fetch data via API (e.g., `/dashboard/org` for org users). Question bank: Stored in DB as JSON field; AI pulls randomly or sequentially.
   - **Implementation**: React components (e.g., `Dashboard.js`) with role-based rendering. Use Material-UI for UI elements.
   - **Production Integration**: Add analytics (e.g., integrate Prometheus for usage metrics). Use RBAC decorators in FastAPI.
3. **Interview Scheduling and Notifications**
   - **Description**: HR schedules via dashboard (select candidate email, time, question bank). Sends email with unique link/code. Reminders 1 hour before.
   - **Explanation**: Generates UUID code for guest access (no login needed for one-time joins). Email includes join link.
   - **Implementation**: `/interview/schedule` endpoint uses Celery for async email (smtplib/SendGrid). Store in PostgreSQL.
   - **Production Integration**: Use SES/Mailgun for reliable emails. Add calendar integration (Google Calendar API) for sync.
4. **AI-Driven Interviews**
   - **Description**: Voice agent asks questions (from bank or LLM-generated), processes responses in real-time. Vision analyzes expressions/confidence/cheating. Live coding editor sends code to backend for LLM evaluation.
   - **Explanation**: AI conversational flow: LLM (Mistral) generates follow-ups based on responses. Vision: Processes frames every 5s for latency. Code: Evaluates logic/syntax against question (e.g., prompt: "Check if this solves [question]").
   - **Implementation**: WebSockets for real-time (code/voice streaming). WebRTC for video. AI services in `services/ai/` (abstract classes for replacement).
   - **Production Integration**: Run AI on dedicated GPU servers (e.g., AWS SageMaker). Use queues (RabbitMQ) for high-load.
5. **Hybrid Mode (Human Involvement)**
   - **Description**: Toggle AI off; Interviewer joins via video call to observe/ask questions.
   - **Explanation**: Seamless switch: If human joins, route voice/video to peer-to-peer.
   - **Implementation**: PeerJS in frontend for WebRTC. Backend signals toggle via WebSockets.
   - **Production Integration**: Use Twilio/Video for scalable WebRTC if PeerJS limits hit.
6. **Report Generation**
   - **Description**: Post-interview report with scores (Q&A: 0-100 based on relevance; Code: Logic/syntax; Vision: Confidence (e.g., average smile/neutral), cheating flags). Recommendation: Proceed/Reject based on thresholds.
   - **Explanation**: Aggregates data from session (stored in Redis temporarily). Emailed to HR/Interviewer.
   - **Implementation**: Celery task (`tasks/report.py`) compiles JSON report, stores in DB.
   - **Production Integration**: Generate PDFs (reportlab lib). Store in S3 for archiving.
7. **Automatic Interview Recording**
   - **Description**: Every interview session is automatically recorded (video and audio streams) for later review by authorized organization members (e.g., HR/Interviewer).
   - **Explanation**: Captures the full WebRTC stream, including candidate video, AI voice, and any human interventions. Recordings are encrypted and linked to the meeting report for auditing/compliance.
   - **Implementation**: In the frontend , use RecordRTC library to start recording on join and stop on end; upload blob to backend endpoint (/interview/record) via FormData. Backend saves to storage (local for dev, S3 for prod) and updates meeting DB with file link. Access restricted via RBAC.
   - **Production Integration**: Use AWS S3/GCP Storage for scalable, secure storage with lifecycle policies (e.g., auto-delete after 30 days). Add deps: `npm i recordrtc` for frontend, `boto3` or similar for backend S3 upload.
8. **Scalability and Modularity**
   - **Description**: Easy model replacement, high performance for real-time.
   - **Explanation**: Abstract AI classes allow swapping (e.g., config env var). Async for concurrency.
   - **Implementation**: Dependency injection in FastAPI.
   - **Production Integration**: See below.
## Tech Stack
- **Backend**: FastAPI (Python) – Async, AI-friendly.
- **Frontend**: html for now must be easily replacebale with next.js – With Material-UI, CodeMirror (editor), Socket.io-client (real-time).
- **Database**: USe SQLite for now but must be easily replacable with PostgreSQL (main), Redis (caching/sessions).
- **AI Models** (Open-Source, Self-Hosted):
  - Voice: Whisper (STT), XTTS-v2 (TTS).
  - Vision: DeepFace (emotions/cheating).
  - LLM:currently use groq api for convo and code evaluation but later on must be easily replaceable to any like ollama , or any other model.
   - AI must be like microservices
  - Via Hugging Face Transformers.
- **Real-Time**: WebSockets (FastAPI), WebRTC (PeerJS).
- **Tasks**: Celery + RabbitMQ (async emails/reports).
- **Deployment**: Docker/Kubernetes.
- **Security**: JWT, OAuth, HTTPS.
- **Live Coding Editor**: Based on 2026 research (sources: TechRadar, Replit Blog, Builder.io, Crozdesk), the best free open-source editor for real-time collaborative coding in web apps is Monaco Editor (MIT license, powers VS Code). It offers superior features like IntelliSense, multi-language support (87+ langs), diff views, and easy WebSocket integration for collab. Alternatives like CodeMirror (lightweight, MIT) or Ace (BSD) are viable but less feature-rich. In this app, replace CodeMirror in `InterviewRoom.js` with Monaco (@monaco-editor/react) for better UX: Install via `npm install @monaco-editor/react`, then use `<Editor />` component with onChange streaming via WebSockets. This ensures low-latency sharing and syntax highlighting during interviews.
## Folder Structure

Below just showing an example , you dont have to follow that exactly but folder structure must be enterprise level 

backend and frontend folder must be there
within which proper production ready folder structure must be followed for fast api


Focus on Fast api backend development first, then frontend currently give html must be easily replaceable with next js 

