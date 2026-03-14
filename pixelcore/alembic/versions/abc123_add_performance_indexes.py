"""Add performance indexes for query optimization.

This migration adds composite indexes to improve query performance:
- interview_messages: (interview_id, timestamp) for time-range queries
- vision_logs: (interview_id, timestamp) for time-range queries  
- users: (organisation_id, role) for org-based user queries

Revision ID: abc123
Revises: 157a44e8f90c
Create Date: 2026-03-14
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'abc123'
down_revision: Union[str, None] = '157a44e8f90c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for interview_messages - efficient time-range queries
    op.create_index(
        'ix_interview_messages_interview_timestamp',
        'interview_messages',
        ['interview_id', 'timestamp'],
        unique=False
    )
    
    # Composite index for vision_logs - efficient time-range queries
    op.create_index(
        'ix_vision_logs_interview_timestamp',
        'vision_logs',
        ['interview_id', 'timestamp'],
        unique=False
    )
    
    # Composite index for users - efficient org-based queries with role filter
    op.create_index(
        'ix_users_organisation_role',
        'users',
        ['organisation_id', 'role'],
        unique=False
    )
    
    # Index for interview_interviewers - efficient interviewer assignment queries
    op.create_index(
        'ix_interview_interviewers_interviewer',
        'interview_interviewers',
        ['interviewer_id'],
        unique=False
    )
    
    # Index for interview_interviewers - efficient interview lookup
    op.create_index(
        'ix_interview_interviewers_interview',
        'interview_interviewers',
        ['interview_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_interview_interviewers_interview', table_name='interview_interviewers')
    op.drop_index('ix_interview_interviewers_interviewer', table_name='interview_interviewers')
    op.drop_index('ix_users_organisation_role', table_name='users')
    op.drop_index('ix_vision_logs_interview_timestamp', table_name='vision_logs')
    op.drop_index('ix_interview_messages_interview_timestamp', table_name='interview_messages')
