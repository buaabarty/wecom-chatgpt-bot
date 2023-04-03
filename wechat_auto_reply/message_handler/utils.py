import threading
import time

class ThreadSafeDict(dict):
    def __init__(self, *args, **kwargs):
        super(ThreadSafeDict, self).__init__(*args, **kwargs)
        self._lock = threading.Lock()

    def __setitem__(self, key, value):
        with self._lock:
            super(ThreadSafeDict, self).__setitem__(key, value)

    def __getitem__(self, key):
        with self._lock:
            return super(ThreadSafeDict, self).__getitem__(key)

class ExpiringDict:
    def __init__(self, expiration_time):
        self.expiration_time = expiration_time
        self.data = ThreadSafeDict()
        self.timestamps = ThreadSafeDict()

    def set(self, key, value):
        self.data[key] = value
        self.timestamps[key] = time.time()

    def get(self, key):
        if key in self.data:
            if time.time() - self.timestamps[key] < self.expiration_time:
                return self.data[key]
            else:
                self.delete(key)
        return None

    def delete(self, key):
        if key in self.data:
            del self.data[key]
            del self.timestamps[key]
