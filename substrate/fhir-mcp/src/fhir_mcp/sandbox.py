"""Sandbox for Level 3 code mode: runs model-written code in its own process.

This restricts what the code can do - no filesystem access, no network beyond
the FHIR server, a CPU/memory/wall-clock budget, no imports beyond what's
already provided - by running it in a fresh subprocess with a locked-down
`exec()` namespace. This is a capability restriction, not a full OS-level
security boundary: a genuinely adversarial script can still find gaps in a
Python-level restriction like this one (CPython was never designed as a
security boundary - see PEP 551). What this defends against is a buggy or
overly broad script written for a real clinical question, not a deliberate
sandbox escape attempt. A tool built for real OS-level isolation (e.g.
Anthropic's sandbox-runtime, using bubblewrap/network namespaces) or a
disposable container per execution is the next hardening step if this is
ever exposed to untrusted input.
"""

from __future__ import annotations

import asyncio
import sys

from .config import MAX_PAGE_SIZE

_CPU_SECONDS = 5
_MEMORY_BYTES = 256 * 1024 * 1024
_DEFAULT_TIMEOUT_SECONDS = 10.0

# Rendered once per call with the model's code embedded via repr(), which
# escapes quotes/backslashes/newlines correctly - the standard, safe way to
# embed arbitrary text as a Python string literal in generated source. No
# shell is involved anywhere in running this (see run_sandboxed), so there is
# no shell-injection surface either.
_BOOTSTRAP_TEMPLATE = '''
import resource as _resource
try:
    _resource.setrlimit(_resource.RLIMIT_CPU, ({cpu_seconds}, {cpu_seconds}))
except (ValueError, OSError):
    pass
try:
    _resource.setrlimit(_resource.RLIMIT_AS, ({memory_bytes}, {memory_bytes}))
except (ValueError, OSError):
    pass

import httpx as _httpx
from fhir_mcp.narrative import narrate as _narrate

_BASE_URL = {base_url!r}
_MAX_COUNT = {max_count}


def _get(_path, _params=None):
    _resp = _httpx.get(
        _BASE_URL + _path,
        params=_params,
        # Bounded by the overall wall-clock budget the caller already
        # enforces around this whole process - a single request timeout
        # longer than that budget could never be the thing that actually
        # fires, so there is no separate, larger number to keep in sync here.
        timeout={http_timeout_seconds},
        headers={{"Accept": "application/fhir+json"}},
    )
    _resp.raise_for_status()
    return _resp.json()


class _Fhir:
    """Data access for the sandboxed script.

    Returns plain structured data (dicts/lists) for the script to compute
    over - call .narrate() to format a final answer as prose before printing
    it, rather than printing raw structured data directly. No pagination:
    this fetches one page of up to _MAX_COUNT resources, same cap as
    search_resources, and has no equivalent of get_next_page - narrow the
    search instead of trying to page through everything.
    """

    def search(self, resource_type, params=None, count=20):
        p = dict(params or {{}})
        p["_count"] = min(count, _MAX_COUNT)
        p.setdefault("_total", "accurate")
        bundle = _get("/" + resource_type, p)
        resources = [e["resource"] for e in bundle.get("entry", []) if e.get("resource")]
        return {{
            "total_matching": bundle.get("total"),
            "returned": len(resources),
            "resources": resources,
        }}

    def get_by_id(self, resource_type, resource_id):
        return _get("/" + resource_type + "/" + resource_id)

    def narrate(self, resources, resource_type):
        return _narrate(resources, resource_type)


fhir = _Fhir()

import builtins as _builtins
import datetime as _datetime_module

_SAFE_NAMES = (
    "print", "len", "range", "sorted", "min", "max", "sum", "enumerate", "zip",
    "map", "filter", "str", "int", "float", "bool", "list", "dict", "set",
    "tuple", "abs", "round", "any", "all", "isinstance", "repr",
    "Exception", "ValueError", "KeyError", "TypeError", "StopIteration",
)
_safe_builtins = {{n: getattr(_builtins, n) for n in _SAFE_NAMES if hasattr(_builtins, n)}}

exec(
    compile({user_code!r}, "<sandbox>", "exec"),
    {{"__builtins__": _safe_builtins, "fhir": fhir, "datetime": _datetime_module}},
)
'''


class SandboxError(Exception):
    """The sandboxed script failed, timed out, or produced no output."""


async def run_sandboxed(
    code: str, base_url: str, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
) -> str:
    """Run `code` in a locked-down subprocess and return what it printed.

    Args:
        code: Python source the model wrote. Runs with no filesystem access,
            no imports beyond what's already provided, and a CPU/memory/
            wall-clock budget - see this module's docstring for exactly what
            that does and doesn't defend against.
        base_url: The FHIR server the sandboxed `fhir` object talks to.
        timeout_seconds: Wall-clock budget. A script blocked on a slow
            request (not just a busy loop, which the CPU limit already
            catches) is killed once this elapses.

    Raises:
        SandboxError: the script raised, was killed for exceeding a limit,
            or printed nothing at all.
    """
    script = _BOOTSTRAP_TEMPLATE.format(
        cpu_seconds=_CPU_SECONDS,
        memory_bytes=_MEMORY_BYTES,
        base_url=base_url,
        max_count=MAX_PAGE_SIZE,
        # Leaves headroom for the process to actually receive SIGKILL/return
        # before the outer wait_for below gives up - a request timeout equal
        # to the whole budget could still lose that race.
        http_timeout_seconds=max(timeout_seconds - 1, 1),
        user_code=code,
    )

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",  # ignores PYTHONPATH/user site-packages; the venv's own
        # packages (fhir_mcp, httpx) still resolve via sys.executable itself.
        "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(script.encode()), timeout=timeout_seconds
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise SandboxError(
            f"The script did not finish within {timeout_seconds:.0f} seconds and was "
            "stopped. Narrow the search or reduce the amount of work the script does."
        ) from exc

    if proc.returncode != 0:
        # A negative returncode means the OS killed the process with a signal
        # rather than the script raising a catchable exception - stderr is
        # empty in that case, so the signal itself is the only information
        # there is. SIGXCPU (24) is what RLIMIT_CPU sends when exceeded;
        # anything else is reported by number since the cause isn't known.
        if proc.returncode is not None and proc.returncode < 0:
            signal_num = -proc.returncode
            if signal_num == 24:
                raise SandboxError(
                    "The script was stopped for using too much CPU time. Reduce the "
                    "amount of work it does - fewer resources fetched, less looping "
                    "over them - rather than retrying the same script unchanged."
                )
            raise SandboxError(
                f"The script was terminated by the operating system (signal {signal_num}), "
                "likely for exceeding a resource limit. Reduce the amount of work it does."
            )
        raise SandboxError(
            "The script failed:\n" + stderr.decode(errors="replace").strip()[-4000:]
        )

    output = stdout.decode(errors="replace").strip()
    if not output:
        raise SandboxError(
            "The script ran successfully but printed nothing. End it with a print() "
            "statement stating the answer - only what the script prints is returned, "
            "not its return value."
        )
    return output


__all__ = ["SandboxError", "run_sandboxed"]
