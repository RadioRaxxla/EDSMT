"""Loaded by Python itself in every check run_all.py starts (this folder is
put on the module path): a check may connect to this machine and nowhere
else. See tests/test_offline.py."""
import os
import socket

GUARDED = True
# A proxy set for this machine would carry a request out from a local
# address, so none is used in a check.
for _name in list(os.environ):
    if _name.lower() in ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy"):
        del os.environ[_name]
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "*"
_LOCAL = ("localhost", "::1", "0.0.0.0", "")
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def _is_local(address):
    if not isinstance(address, tuple) or not address:
        return True          # a socket file on this machine
    host = str(address[0]).lower()
    return host in _LOCAL or host.startswith("127.")


def _local_only(self, address, *args, **kwargs):
    if _is_local(address):
        return _connect(self, address, *args, **kwargs)
    raise OSError("no network in a test run (%s)" % (address[0],))


def _local_only_ex(self, address, *args, **kwargs):
    if _is_local(address):
        return _connect_ex(self, address, *args, **kwargs)
    return 10065             # no route to host


socket.socket.connect = _local_only
socket.socket.connect_ex = _local_only_ex
