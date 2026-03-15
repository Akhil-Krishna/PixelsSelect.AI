'use client';

import { useState, useEffect } from 'react';

interface LandingPageProps {
    onLogin: () => void;
    onRegister: () => void;
}

export function LandingPage({ onLogin, onRegister }: LandingPageProps) {
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 40);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <div className="landing">
            {/* ── Navbar ── */}
            <nav className={`landing-nav${scrolled ? ' scrolled' : ''}`}>
                <div className="landing-container landing-nav-inner">
                    <div className="landing-brand">
                        <img src="/logo.png" alt="PixelHire"  style={{ width: 36, height: 36, borderRadius: 10, objectFit: 'contain' }} />
                        <span className="landing-brand-text" style={{ fontWeight: 800, letterSpacing: '-0.02em' }}>Pixel<span style={{ fontWeight: 600, opacity: 0.85 }}>Hire</span><span className="landing-brand-ai">.AI</span></span>
                    </div>
                    <div className="landing-nav-links">
                        <a href="#features">Features</a>
                        <a href="#how-it-works">How It Works</a>
                        <a href="#stats">Results</a>
                    </div>
                    <div className="landing-nav-actions">
                        <button className="landing-btn-ghost" onClick={onLogin}>Log In</button>
                        <button className="landing-btn-primary" onClick={onRegister}>Get Started</button>
                    </div>
                    {/* Mobile menu button */}
                    <button className="landing-mobile-menu" onClick={() => {
                        document.querySelector('.landing-nav-links')?.classList.toggle('show');
                    }}>
                        <i className="fas fa-bars" />
                    </button>
                </div>
            </nav>

            {/* ── Hero ── */}
            <section className="landing-hero">
                <div className="landing-hero-bg">
                    <div className="landing-hero-orb landing-hero-orb-1" />
                    <div className="landing-hero-orb landing-hero-orb-2" />
                    <div className="landing-hero-orb landing-hero-orb-3" />
                </div>
                <div className="landing-container landing-hero-content">
                    <div className="landing-hero-badge">
                        <i className="fas fa-bolt" /> AI-Powered Interview Platform
                    </div>
                    <h1 className="landing-hero-title">
                        Hire Smarter with<br />
                        <span className="landing-gradient-text">AI-Driven Interviews</span>
                    </h1>
                    <p className="landing-hero-desc">
                        Automate your interview process with real-time AI analysis, emotion detection,
                        integrity monitoring, and instant scoring — all in one platform.
                    </p>
                    <div className="landing-hero-actions">
                        <button className="landing-btn-primary landing-btn-lg" onClick={onRegister}>
                            <i className="fas fa-rocket" /> Start 
                        </button>
                        <button className="landing-btn-outline landing-btn-lg" onClick={onLogin}>
                            <i className="fas fa-sign-in-alt" /> Sign In
                        </button>
                    </div>
                    <div className="landing-hero-trust">
                        <span>✓ No credit card required</span>
                        <span>✓ Setup in 2 minutes</span>
                        <span>✓ Free for small teams</span>
                    </div>
                </div>
            </section>

            {/* ── Logos / Social Proof ── */}
            <section className="landing-logos">
                <div className="landing-container">
                    <p className="landing-logos-label">Trusted by teams focused on smarter hiring</p>
                    <div className="landing-logos-row">
                        {['Startups', 'Enterprises', 'HR Teams', 'Tech Companies', 'Recruiters'].map(l => (
                            <div key={l} className="landing-logo-item">{l}</div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── Features ── */}
            <section className="landing-features" id="features">
                <div className="landing-container">
                    <div className="landing-section-header">
                        <div className="landing-section-badge">Features</div>
                        <h2 className="landing-section-title">Everything you need for<br /><span className="landing-gradient-text">modern hiring</span></h2>
                        <p className="landing-section-desc">
                            From scheduling to scoring, PixelHire handles the entire interview lifecycle.
                        </p>
                    </div>
                    <div className="landing-features-grid">
                        {[
                            { icon: 'fa-robot', title: 'AI Interviewer', desc: 'Intelligent AI conducts structured interviews with adaptive follow-up questions based on candidate responses.', color: '#4F46E5' },
                            { icon: 'fa-video', title: 'Live Video Rooms', desc: 'Real-time video interviews with multi-participant support. HR and interviewers can join, observe, and collaborate.', color: '#7C3AED' },
                            { icon: 'fa-face-smile', title: 'Emotion Analysis', desc: 'Real-time facial expression analysis measures confidence, engagement, and stress levels throughout the interview.', color: '#EC4899' },
                            { icon: 'fa-shield-halved', title: 'Integrity Detection', desc: 'Monitors for tab-switching, multiple faces, gaze direction, and other cheating indicators automatically.', color: '#F59E0B' },
                            { icon: 'fa-code', title: 'Live Code Editor', desc: 'Built-in code editor for technical assessments. AI evaluates code quality, logic, and efficiency in real-time.', color: '#10B981' },
                            { icon: 'fa-chart-line', title: 'Instant Scoring', desc: 'Comprehensive scoring across answers, coding, emotion, and integrity — with AI-generated feedback for every candidate.', color: '#3B82F6' },
                            { icon: 'fa-building', title: 'Department Management', desc: 'Organize teams into departments with labeled question banks, scoped interviewers, and department-level reporting.', color: '#8B5CF6' },
                            { icon: 'fa-envelope', title: 'Automated Invitations', desc: 'Magic-link invites, scheduled reminders, and interviewer notifications — fully automated email workflow.', color: '#06B6D4' },
                        ].map(f => (
                            <div key={f.title} className="landing-feature-card">
                                <div className="landing-feature-icon" style={{ background: `${f.color}15`, color: f.color }}>
                                    <i className={`fas ${f.icon}`} />
                                </div>
                                <h3 className="landing-feature-title">{f.title}</h3>
                                <p className="landing-feature-desc">{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── How It Works ── */}
            <section className="landing-how" id="how-it-works">
                <div className="landing-container">
                    <div className="landing-section-header">
                        <div className="landing-section-badge">How It Works</div>
                        <h2 className="landing-section-title">From schedule to hire in<br /><span className="landing-gradient-text">three simple steps</span></h2>
                    </div>
                    <div className="landing-steps">
                        {[
                            { num: '01', title: 'Schedule & Invite', desc: 'Create an interview, pick from your department question banks, assign interviewers, and the candidate receives a magic-link invite.', icon: 'fa-calendar-plus' },
                            { num: '02', title: 'AI Conducts Interview', desc: 'The AI interviewer asks questions, monitors emotions, detects integrity issues, and evaluates coding skills — all in real-time.', icon: 'fa-microchip' },
                            { num: '03', title: 'Review & Decide', desc: 'Get instant scores, detailed AI feedback, and full recordings. Department interviewers can view reports for all their team\'s interviews.', icon: 'fa-chart-pie' },
                        ].map((step, i) => (
                            <div key={step.num} className="landing-step">
                                <div className="landing-step-num">{step.num}</div>
                                <div className="landing-step-icon">
                                    <i className={`fas ${step.icon}`} />
                                </div>
                                <h3 className="landing-step-title">{step.title}</h3>
                                <p className="landing-step-desc">{step.desc}</p>
                                {i < 2 && <div className="landing-step-connector" />}
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── Stats ── */}
            <section className="landing-stats" id="stats">
                <div className="landing-container">
                    <div className="landing-stats-grid">
                        {[
                            { val: '10x', label: 'Faster Screening', icon: 'fa-bolt' },
                            { val: '95%', label: 'Accuracy Rate', icon: 'fa-bullseye' },
                            { val: '60%', label: 'Cost Reduction', icon: 'fa-arrow-trend-down' },
                            { val: '24/7', label: 'Available Anytime', icon: 'fa-clock' },
                        ].map(s => (
                            <div key={s.label} className="landing-stat-card">
                                <i className={`fas ${s.icon} landing-stat-icon`} />
                                <div className="landing-stat-val">{s.val}</div>
                                <div className="landing-stat-label">{s.label}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── CTA ── */}
            <section className="landing-cta">
                <div className="landing-container landing-cta-inner">
                    <h2 className="landing-cta-title">Ready to transform your hiring?</h2>
                    <p className="landing-cta-desc">
                        Join forward-thinking companies using AI to find the best talent faster.
                    </p>
                    <div className="landing-hero-actions">
                        <button className="landing-btn-white landing-btn-lg" onClick={onRegister}>
                            <i className="fas fa-rocket" /> Register Your Organisation
                        </button>
                        <button className="landing-btn-outline-white landing-btn-lg" onClick={onLogin}>
                            <i className="fas fa-sign-in-alt" /> Sign In
                        </button>
                    </div>
                </div>
            </section>

            {/* ── Footer ── */}
            <footer className="landing-footer">
                <div className="landing-container landing-footer-inner">
                    <div className="landing-footer-brand">
                        <div className="landing-brand">
                            <img src="/logo.png" alt="PixelHire" style={{ width: 28, height: 28, borderRadius: 8, objectFit: 'contain' }} />
                            <span className="landing-brand-text" style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.02em' }}>Pixel<span style={{ fontWeight: 600, opacity: 0.85 }}>Hire</span><span className="landing-brand-ai">.AI</span></span>
                        </div>
                        <p className="landing-footer-tagline">AI-powered interviews that find the best talent.</p>
                    </div>
                    <div className="landing-footer-links">
                        <a href="#features">Features</a>
                        <a href="#how-it-works">How It Works</a>
                        <a href="#stats">Results</a>
                    </div>
                    <div className="landing-footer-copy">
                        © {new Date().getFullYear()} PixelHire.AI — All rights reserved.
                    </div>
                </div>
            </footer>
        </div>
    );
}
