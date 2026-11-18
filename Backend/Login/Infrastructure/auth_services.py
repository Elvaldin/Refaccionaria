import bcrypt

from Application.login_use_case import PasswordHasher

class BcryptPasswordHasher(PasswordHasher):
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        try:
            return bcrypt.checkpw(plain_bytes, hashed_bytes)
        except Exception:
            return False

    def hash(self, plain_password: str) -> str:
        return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')