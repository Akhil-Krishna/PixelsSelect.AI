export interface User {
    id: string;
    full_name: string;
    email: string;
    role: 'admin' | 'hr' | 'interviewer' | 'candidate';
    is_active: boolean;
    organisation?: { id: string; name: string };
}

export interface Interview {
    id: string;
    title: string;
    job_role: string;
    status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
    scheduled_at: string;
    duration_minutes: number;
    description?: string;
    candidate?: User;
    access_token: string;
    overall_score?: number;
    answer_score?: number;
    code_score?: number;
    emotion_score?: number;
    integrity_score?: number;
    ai_feedback?: string;
    has_recording?: boolean;
    resume_path?: string;
    passed?: boolean;
    temp_password?: string;
    ai_paused?: boolean;
    started_at?: string;
}

export interface Message {
    id: string;
    role: 'ai' | 'candidate' | 'interviewer';
    content: string;
    code_snippet?: string;
    timestamp?: string;
}

export interface InterviewSession {
    id: string;
    title: string;
    job_role: string;
    duration_minutes: number;
    scheduled_at: string;
    status: string;
    ai_paused?: boolean;
    started_at?: string;
    has_recording?: boolean;
    candidate?: { full_name: string; email: string };
    // Scores (populated after completion)
    answer_score?: number;
    code_score?: number;
    emotion_score?: number;
    integrity_score?: number;
    overall_score?: number;
    passed?: boolean;
    ai_feedback?: string;
}

export interface Metrics {
    confidence?: number;
    engagement?: number;
    stress?: number;
    cheating_score?: number;
    dominant_emotion?: string;
    face_count?: number;
    gaze_ok?: boolean;
    frames_analyzed?: number;
    look_away_count?: number;
    multi_face_count?: number;
    tab_switches?: number;
}

export interface FlagItem {
    id: number;
    text: string;
    type: 'warn' | 'danger' | 'info' | 'success';
    icon: string;
    time: string;
}

export interface ToastItem {
    id: number;
    msg: string;
    type: 'success' | 'error' | 'info' | 'warning';
}

export interface StatCard {
    icon: string;
    bg: string;
    ic: string;
    val: number;
    lbl: string;
}
