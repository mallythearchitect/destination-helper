"""UUIDv7 (RFC 9562): time-ordered ids. Python 3.13 has no uuid.uuid7 yet.

Monotonic within this process: two ids made in the same millisecond still
sort in the order they were made (the 12-bit rand_a field is a counter that
resets on each new millisecond), so ORDER BY id is the order of events.
"""
from __future__ import annotations

import os
import threading
import time

_lock = threading.Lock()
_last_ms = 0
_seq = 0


def uuid7() -> str:
    global _last_ms, _seq
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms <= _last_ms:
            ms = _last_ms
            _seq += 1
            if _seq > 0xFFF:          # counter full: borrow the next millisecond
                ms += 1
                _seq = 0
        else:
            _seq = int.from_bytes(os.urandom(2), "big") & 0x7FF   # random start, room to count up
        _last_ms = ms
        seq = _seq
    b = bytearray(ms.to_bytes(6, "big") + seq.to_bytes(2, "big") + os.urandom(8))
    b[6] = (b[6] & 0x0F) | 0x70  # version 7 in the top nibble of rand_a
    b[8] = (b[8] & 0x3F) | 0x80  # RFC 4122 variant
    h = b.hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
