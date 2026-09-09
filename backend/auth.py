"""Shared internal-workspace session; use a private reverse proxy for team deployment."""
import hashlib
import hmac
import secrets
import time


class Sessions:
    def __init__(self, root, password):
        self.password=password
        secret_file=root/'session.key'
        if not secret_file.exists():
            secret_file.write_bytes(secrets.token_bytes(32))
            secret_file.chmod(0o600)
        self.secret=secret_file.read_bytes()
        self.attempts={}

    def issue(self):
        value=f'{int(time.time())+86400*7}.{secrets.token_hex(16)}'
        return value+'.'+hmac.new(self.secret,value.encode(),hashlib.sha256).hexdigest()

    def valid(self,token):
        try:
            expiry,nonce,signature=token.split('.')
            value=expiry+'.'+nonce
            return int(expiry)>time.time() and hmac.compare_digest(signature,hmac.new(self.secret,value.encode(),hashlib.sha256).hexdigest())
        except (ValueError,AttributeError):
            return False

    def login(self,password,ip):
        now=time.time()
        self.attempts={k:[t for t in v if now-t<60] for k,v in self.attempts.items() if any(now-t<60 for t in v)}
        prior=self.attempts.setdefault(ip,[])
        if len(prior)>=10:
            raise ValueError('Too many attempts. Wait one minute and try again.')
        prior.append(now)
        return hmac.compare_digest(password.encode(),self.password.encode())
