"""empty message

Revision ID: 4b67927c17ee
Revises: cfb2e1fdcd67
Create Date: 2025-02-11 23:04:32.214530

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b67927c17ee'
down_revision = 'cfb2e1fdcd67'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('profile_info', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=15), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('profile_info', schema=None) as batch_op:
        batch_op.drop_column('phone')

    # ### end Alembic commands ###
