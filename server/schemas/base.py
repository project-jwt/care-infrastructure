# schemas/base.py — shared parent for every request/response schema
#
# The README's rule "snake_case in Python, camelCase in the API contract" is
# implemented HERE, once. Every schema inherits CamelModel instead of BaseModel
# and gets the translation for free.

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        # Generate a camelCase alias for every field: full_name <-> fullName.
        # Aliases are what the JSON layer uses, both parsing and serializing.
        alias_generator=to_camel,
        # Also allow the original snake_case name when constructing in Python:
        # UserOut(full_name=...) — without this, only the alias would work.
        populate_by_name=True,
        # Allow building a schema FROM AN OBJECT's attributes (our SQLAlchemy
        # User), not just from dicts. This is what lets response_model=UserOut
        # accept the ORM object a route returns.
        from_attributes=True,
    )
