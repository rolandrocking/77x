import logging

from alembic import command
from alembic.config import Config


def apply_migrations():
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.propagate = True
    # Path to your Alembic config file
    alembic_cfg = Config("alembic.ini")
    # Run the migrations
    command.upgrade(alembic_cfg, "head")
