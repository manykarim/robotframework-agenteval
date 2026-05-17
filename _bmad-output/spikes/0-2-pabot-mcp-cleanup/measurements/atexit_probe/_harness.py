"""Atexit-probe harness — spawns 3 MCP servers via MCPLifecycleManager, then waits.

INSTALL_SIGTERM_HANDLER env var controls whether SIGTERM is converted to sys.exit:
    INSTALL_SIGTERM_HANDLER=1 → install a signal handler that calls sys.exit(0)
        Production pattern. atexit will fire. MCP grandchildren should be reaped.
    INSTALL_SIGTERM_HANDLER=0 → use Python's default SIGTERM handler
        Process dies without running atexit. MCP grandchildren leak.

This distinguishes 'atexit infrastructure works' from 'the verdict's defense-in-depth
claim requires a signal handler to be installed at the listener layer.'
"""
import os
import signal
import sys
import time
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent.parent.parent  # measurements/atexit_probe → spike dir
sys.path.insert(0, str(SPIKE_DIR))

from context_prototype import MCPLifecycleManager, ServerSpec

# INSTALL_SIGTERM_HANDLER controls both:
#  (a) MCPLifecycleManager's auto-installed handler (install_sigterm_handler kwarg)
#  (b) any extra harness-level handler (none here; the manager's is sufficient)
# Setting "0" disables the auto-install so scenario B can demonstrate the "without handler, leaks" case.
install_handler = os.environ.get("INSTALL_SIGTERM_HANDLER", "1") == "1"

spec = ServerSpec(
    command=[sys.executable, "-m", "servers.echo_server"],
    marker="SPIKE-0-2-ECHO",
)
mgr = MCPLifecycleManager(scope="test", default_spec=spec, install_sigterm_handler=install_handler)

for i in range(3):
    mgr.acquire(test_id=f"atexit-probe-{i}", suite_id="atexit-probe-suite")

sys.stdout.write(f"HARNESS_READY pid={os.getpid()}\n")
sys.stdout.flush()
time.sleep(60)
