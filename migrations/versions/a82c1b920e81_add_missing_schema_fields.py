"""add missing fields and tables

Revision ID: a82c1b920e81
Revises: f2e9344eb752
Create Date: 2026-08-25 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'a82c1b920e81'
down_revision = 'f2e9344eb752'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Update registration table with role and verified_doctor
    with op.batch_alter_table('registration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), server_default='patient', nullable=False))
        batch_op.add_column(sa.Column('verified_doctor', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # 2. Update profile_info with consultation_fee
    with op.batch_alter_table('profile_info', schema=None) as batch_op:
        batch_op.add_column(sa.Column('consultation_fee', sa.Float(), server_default='1000.0', nullable=True))

    # 3. Create appointments table
    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('registration.uid'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('registration.uid'), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('patient_name', sa.String(length=120), nullable=False),
        sa.Column('patient_email', sa.String(length=120), nullable=False),
        sa.Column('patient_phone', sa.String(length=25), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('preferred_date', sa.Date(), nullable=True),
        sa.Column('preferred_time', sa.String(length=50), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=True),
        sa.Column('scheduled_time', sa.String(length=50), nullable=True),
        sa.Column('doctor_notes', sa.Text(), nullable=True),
        sa.Column('fee_amount', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('payment_status', sa.String(length=20), server_default='unpaid', nullable=False),
        sa.Column('transaction_id', sa.String(length=100), nullable=True),
        sa.Column('bank_tran_id', sa.String(length=100), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('payment_amount', sa.Float(), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.now),
        sa.Column('updated_at', sa.DateTime(), default=datetime.now),
    )

    # 4. Update prescription table with appointment_id
    with op.batch_alter_table('prescription', schema=None) as batch_op:
        batch_op.add_column(sa.Column('appointment_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_prescription_appointment', 'appointments', ['appointment_id'], ['id'])

    # 5. Create payment_transactions table
    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('appointment_id', sa.Integer(), sa.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('registration.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('registration.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('tran_id', sa.String(length=100), unique=True, nullable=False, index=True),
        sa.Column('val_id', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='BDT', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='initiated', nullable=False),
        sa.Column('card_type', sa.String(length=50), nullable=True),
        sa.Column('card_no', sa.String(length=50), nullable=True),
        sa.Column('bank_tran_id', sa.String(length=100), nullable=True),
        sa.Column('card_issuer', sa.String(length=100), nullable=True),
        sa.Column('card_brand', sa.String(length=50), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.now),
        sa.Column('updated_at', sa.DateTime(), default=datetime.now),
    )

    # 6. Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('registration.uid'), nullable=False),
        sa.Column('appointment_id', sa.Integer(), sa.ForeignKey('appointments.id'), nullable=True),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('event_type', sa.String(length=50), server_default='general', nullable=False),
        sa.Column('link_url', sa.String(length=255), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.now),
    )


def downgrade():
    op.drop_table('notifications')
    op.drop_table('payment_transactions')
    with op.batch_alter_table('prescription', schema=None) as batch_op:
        batch_op.drop_constraint('fk_prescription_appointment', type_='foreignkey')
        batch_op.drop_column('appointment_id')
    op.drop_table('appointments')
    with op.batch_alter_table('profile_info', schema=None) as batch_op:
        batch_op.drop_column('consultation_fee')
    with op.batch_alter_table('registration', schema=None) as batch_op:
        batch_op.drop_column('verified_doctor')
        batch_op.drop_column('role')
