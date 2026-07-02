# TODO: security helpers.
# Expected:
#   - hash_password(plain) / verify_password(plain, hashed)   via passlib[bcrypt]
#   - create_access_token(user_id, role)                       via python-jose, HS256
#   - decode_token(token)                                       returns payload or raises

from passlib.context import CryptContext
from jose import jwt
