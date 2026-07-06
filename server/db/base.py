# db/base.py — the shared parent class for every model in server/models/
#
# There's no Express equivalent because raw pg has no ORM layer. If you've seen
# Sequelize, this is like the `sequelize` instance every model registers on.
#
# Inheriting from Base does two things for a model class:
#   1. It makes the class a "declarative model": SQLAlchemy reads the class's
#      __tablename__ and Mapped[...] attributes and builds a table definition.
#   2. It registers that table in Base.metadata — a catalog of every table the
#      app knows about. That's what lets db/seed.py create ALL tables with one
#      call (Base.metadata.create_all) instead of hand-writing CREATE TABLE sql.

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Subclass this in every model file: class User(Base): ..."""
