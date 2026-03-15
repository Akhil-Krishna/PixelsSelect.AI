"""add_multi_face_count_to_interviews

Revision ID: 80d8179e5c33
Revises: 
Create Date: 2026-03-11 23:11:47.253287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '80d8179e5c33'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Custom enum types ──────────────────────────────────────────────────
    userrole = postgresql.ENUM(
        'admin', 'hr', 'interviewer', 'candidate',
        name='userrole', create_type=False,
    )
    interviewstatus = postgresql.ENUM(
        'scheduled', 'in_progress', 'completed', 'cancelled',
        name='interviewstatus', create_type=False,
    )
    op.execute("CREATE TYPE IF NOT EXISTS userrole AS ENUM ('admin','hr','interviewer','candidate')")
    op.execute("CREATE TYPE IF NOT EXISTS interviewstatus AS ENUM ('scheduled','in_progress','completed','cancelled')")

    # ── organisations ──────────────────────────────────────────────────────
    op.create_table(
        'organisations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('domain', sa.String(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('plan', sa.String(), nullable=False),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # ── departments ────────────────────────────────────────────────────────
    op.create_table(
        'departments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('organisation_id', sa.String(), nullable=False),
        sa.Column('lead_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
        # lead_id FK added after users table exists
    )

    # ── users ──────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('role', userrole, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('auth_provider', sa.String(), nullable=False),
        sa.Column('invited_by', sa.String(), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('organisation_id', sa.String(), nullable=True),
        sa.Column('department_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
    )

    # Now add the deferred FK from departments.lead_id -> users.id
    op.create_foreign_key('fk_departments_lead_id', 'departments', 'users', ['lead_id'], ['id'])

    # ── idempotency_keys ───────────────────────────────────────────────────
    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('request_hash', sa.String(), nullable=False),
        sa.Column('response_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope', 'key', name='uq_idempotency_scope_key'),
    )

    # ── department_question_banks ──────────────────────────────────────────
    op.create_table(
        'department_question_banks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('department_id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('questions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
    )

    # ── invitations ────────────────────────────────────────────────────────
    op.create_table(
        'invitations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organisation_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('role', userrole, nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('invited_by', sa.String(), nullable=False),
        sa.Column('accepted', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.UniqueConstraint('token_hash'),
    )

    # ── password_reset_tokens ──────────────────────────────────────────────
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('token_hash'),
    )

    # ── interviews ─────────────────────────────────────────────────────────
    op.create_table(
        'interviews',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('job_role', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organisation_id', sa.String(), nullable=True),
        sa.Column('department_id', sa.String(), nullable=True),
        sa.Column('hr_id', sa.String(), nullable=False),
        sa.Column('candidate_id', sa.String(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('status', interviewstatus, nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('question_bank', sa.JSON(), nullable=True),
        sa.Column('resume_path', sa.String(), nullable=True),
        sa.Column('resume_text', sa.Text(), nullable=True),
        sa.Column('enable_emotion_analysis', sa.Boolean(), nullable=False),
        sa.Column('enable_cheating_detection', sa.Boolean(), nullable=False),
        sa.Column('ai_paused', sa.Boolean(), nullable=False),
        sa.Column('tab_switch_count', sa.Integer(), nullable=False),
        sa.Column('manual_questions', sa.JSON(), nullable=True),
        sa.Column('answer_score', sa.Float(), nullable=True),
        sa.Column('code_score', sa.Float(), nullable=True),
        sa.Column('emotion_score', sa.Float(), nullable=True),
        sa.Column('cheating_score', sa.Float(), nullable=True),
        sa.Column('integrity_score', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column('ai_feedback', sa.Text(), nullable=True),
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('weaknesses', sa.JSON(), nullable=True),
        sa.Column('final_hiring_recommendation', sa.String(), nullable=True),
        sa.Column('recommendation_justification', sa.Text(), nullable=True),
        sa.Column('emotion_scores', sa.JSON(), nullable=True),
        sa.Column('transcript', sa.JSON(), nullable=True),
        sa.Column('recording_url', sa.String(), nullable=True),
        sa.Column('recording_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('recording_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id']),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.ForeignKeyConstraint(['hr_id'], ['users.id']),
        sa.ForeignKeyConstraint(['candidate_id'], ['users.id']),
        sa.UniqueConstraint('access_token'),
    )

    # ── interview_interviewers ─────────────────────────────────────────────
    op.create_table(
        'interview_interviewers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('interview_id', sa.String(), nullable=False),
        sa.Column('interviewer_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id']),
        sa.ForeignKeyConstraint(['interviewer_id'], ['users.id']),
    )

    # ── interview_messages ─────────────────────────────────────────────────
    op.create_table(
        'interview_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('interview_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('code_snippet', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id']),
    )

    # ── vision_logs ────────────────────────────────────────────────────────
    op.create_table(
        'vision_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('interview_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dominant_emotion', sa.String(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('stress_score', sa.Float(), nullable=True),
        sa.Column('emotions_raw', sa.JSON(), nullable=True),
        sa.Column('face_count', sa.Integer(), nullable=False),
        sa.Column('gaze_deviation', sa.Float(), nullable=True),
        sa.Column('cheating_flags', sa.JSON(), nullable=True),
        sa.Column('cheating_score', sa.Float(), nullable=False),
        sa.Column('tab_switch_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id']),
    )


def downgrade() -> None:
    op.drop_table('vision_logs')
    op.drop_table('interview_messages')
    op.drop_table('interview_interviewers')
    op.drop_table('interviews')
    op.drop_table('password_reset_tokens')
    op.drop_table('invitations')
    op.drop_table('department_question_banks')
    op.drop_table('idempotency_keys')
    op.drop_constraint('fk_departments_lead_id', 'departments', type_='foreignkey')
    op.drop_table('users')
    op.drop_table('departments')
    op.drop_table('organisations')
    op.execute("DROP TYPE IF EXISTS interviewstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
