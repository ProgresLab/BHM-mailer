"""Offline maintenance fence: bind canonical port and hold the SMTP OS lock."""
from contextlib import contextmanager
import os
from pathlib import Path
import socket


@contextmanager
def stopped_runtime(database):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    handles = []
    try:
        listener.bind(('127.0.0.1', 8000))
        listener.listen(1)
        path = Path(database).resolve().with_suffix(Path(database).suffix+'.worker.lock')
        paths=[path,*path.parent.glob(Path(database).stem+'.imap-*.worker.lock')]
        for lock_path in paths:
            handle = open(lock_path, 'a+b')
            handles.append(handle)
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()
        listener.close()
