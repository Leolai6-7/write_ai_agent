"""Bounded, opt-in JSONL worker transport. No daemon or global model cache.

The caller owns the context lifetime. Only the worker interpreter/encoder is
reused; the worker reloads a fresh graph for each query. Protocol failures stop
the session instead of silently retrying paid requests.
"""

from copy import deepcopy
import json
import subprocess
import threading


class WorkerSessionError(ValueError):
    """The isolated query session is unavailable or violated its contract."""


class JevWorkerSession:
    def __init__(self, *, max_requests: int = 128):
        if type(max_requests) is not int or not 1 <= max_requests <= 128:
            raise ValueError("max_requests must be between 1 and 128")
        self.max_requests = max_requests
        self._process = None
        self._backend = None
        self._worker = None
        self._count = 0
        self._entered = False
        self._closed = False
        self._lock = threading.Lock()

    def __enter__(self):
        if self._entered or self._closed:
            raise WorkerSessionError("Use a new worker session for each context")
        self._entered = True
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._closed = True
        process = self._process
        if process is None:
            return
        # Termination also interrupts a stalled pipe writer/reader. Never wait
        # for a provider request to finish when its enclosing context has ended.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()

    def request(self, config: dict, backend: dict, payload: dict, worker) -> dict:
        if not self._entered or self._closed:
            raise WorkerSessionError("Worker session must be inside its open context")
        if not self._lock.acquire(blocking=False):
            raise WorkerSessionError("Worker session only supports sequential queries")
        try:
            return self._request(config, backend, payload, worker)
        except Exception:
            self.close()
            raise
        finally:
            self._lock.release()

    def _request(self, config, backend, payload, worker):
        if payload.get("action") != "query":
            raise WorkerSessionError("Reusable worker sessions accept queries only")
        if self._count >= self.max_requests:
            raise WorkerSessionError("Worker session request budget exhausted")
        if self._backend is not None and (backend != self._backend or str(worker) != self._worker):
            raise WorkerSessionError("Worker backend changed; start a new session")
        self._count += 1
        wire = json.dumps({**payload, "request_id": self._count}, ensure_ascii=False).encode() + b"\n"
        if len(wire) > 8 * 1024 * 1024:
            raise WorkerSessionError("Worker request exceeds 8 MiB")
        if self._process is None:
            self._backend, self._worker = deepcopy(backend), str(worker)
            self._process = subprocess.Popen(
                [backend["python"], "-I", "-u", str(worker), "--session"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=backend["source"], bufsize=0,
            )
        process = self._process
        reply = {}

        def exchange():
            try:
                view = memoryview(wire)
                while view:
                    written = process.stdin.write(view)
                    if not written:
                        raise BrokenPipeError
                    view = view[written:]
                line = process.stdout.readline(4 * 1024 * 1024 + 1)
                if not line.endswith(b"\n") or len(line) > 4 * 1024 * 1024:
                    raise ValueError("Invalid response frame")
                reply["result"] = json.loads(line)
            except Exception:
                # Never propagate provider output or OS errors containing state.
                reply["failed"] = True

        thread = threading.Thread(target=exchange, daemon=True)
        thread.start()
        thread.join(config["timeout_seconds"])
        if thread.is_alive():
            self.close()
            thread.join(timeout=1)
            raise WorkerSessionError("Jev-Mem worker exceeded timeout_seconds")
        result = reply.get("result")
        if (reply.get("failed") or not isinstance(result, dict)
                or type(result.get("request_id")) is not int
                or result["request_id"] != self._count or result.get("status") != "ok"):
            raise WorkerSessionError("Jev-Mem session returned an invalid response")
        return result
