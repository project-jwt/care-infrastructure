# Import every model module here so a single `import models` registers ALL
# tables in Base.metadata (main.py's create_all relies on this).
#
# ADDING A MODEL? Add its import below or create_all will silently skip its
# table — "why is my table missing" is almost always a missing import here.

from models import user_model  # noqa: F401

# future: contact_model, summary_model, helpline_model
