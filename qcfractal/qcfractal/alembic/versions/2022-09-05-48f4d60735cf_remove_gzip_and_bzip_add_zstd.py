"""remove gzip and bzip, add zstd

Revision ID: 48f4d60735cf
Revises: 8fc81746daa6
Create Date: 2022-09-05 10:11:48.344125

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "48f4d60735cf"
down_revision = "8fc81746daa6"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("ALTER TYPE compressionenum RENAME TO compressionenum_old")
    new_enum = sa.Enum("none", "lzma", "zstd", name="compressionenum")
    new_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("output_store", sa.Column("new_compression", new_enum))
    op.add_column("native_file", sa.Column("new_compression", new_enum))

    op.execute("UPDATE output_store SET new_compression = compression::text::compressionenum")
    op.execute("UPDATE native_file SET new_compression = compression::text::compressionenum")

    op.drop_column("output_store", "compression")
    op.alter_column("output_store", "new_compression", new_column_name="compression")

    op.drop_column("native_file", "compression")
    op.alter_column("native_file", "new_compression", new_column_name="compression", nullable=False)

    op.execute("DROP TYPE compressionenum_old")

    # ### end Alembic commands ###


def downgrade():
    raise RuntimeError("Cannot downgrade")
