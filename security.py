"""Small same-origin/session safeguards without replacing existing authentication."""
from collections import deque
import hashlib, threading, time
from urllib.parse import urlparse

class LoginThrottle:
    def __init__(self):
        self.lock=threading.Lock(); self.failures={}; self.window=600
    def _keys(self, ip, username):
        digest=hashlib.sha256(username.strip().casefold().encode()).hexdigest()
        return [('account',digest),('ip',ip)]
    def blocked(self, ip, username):
        now=time.time()
        with self.lock:
            for key in list(self.failures):
                while self.failures[key] and self.failures[key][0]<=now-self.window: self.failures[key].popleft()
                if not self.failures[key]: del self.failures[key]
            keys=self._keys(ip,username)
            return any(len(self.failures.get(key,())) >= (5 if key[0]=='account' else 50) for key in keys)
    def record(self, ip, username, success):
        with self.lock:
            keys=self._keys(ip,username)
            if success: self.failures.pop(keys[0],None)
            else:
                # Bounded memory; IP budget limits distinct-username sprays.
                if len(self.failures)>10000:
                    # Do not erase every budget under a username spray.
                    oldest=min(self.failures,key=lambda key:self.failures[key][-1])
                    del self.failures[oldest]
                for key in keys: self.failures.setdefault(key,deque()).append(time.time())

LOGIN_THROTTLE=LoginThrottle()

def validate_password(password):
    if not isinstance(password,str) or not 10<=len(password)<=256 or not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError('Use 10–256 characters including an uppercase letter, a lowercase letter and a number.')

def same_origin(headers):
    if headers.get('Sec-Fetch-Site','').lower()=='cross-site': return False
    origin=headers.get('Origin')
    if origin is None: return True  # CLI/local API clients do not use ambient browser cookies.
    parsed=urlparse(origin)
    return parsed.scheme in ('http','https') and parsed.netloc.casefold()==headers.get('Host','').casefold() and parsed.path in ('','/') and not parsed.username and not parsed.password

def session_cookie(token, secure=False):
    return f'ghz_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=1209600'+('; Secure' if secure else '')
