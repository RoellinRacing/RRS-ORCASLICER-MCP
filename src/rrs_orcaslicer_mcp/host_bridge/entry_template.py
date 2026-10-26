# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.orcaslicer.plugin]
# name = "RRS OrcaSlicer Bridge"
# description = "Local MCP bridge: live project/preset reads and staged preset transactions."
# author = "RoellinRacing"
# version = "0.5.0"
# ///
"""Generated standalone plugin for the official Orca Python host.

Source, architecture and tests: https://github.com/RoellinRacing/RRS-ORCASLICER-MCP
AGPL-3.0-or-later. No network listener, arbitrary eval or printer-control endpoint.
Start with Plugins -> Run. Closing its panel stops new requests.
"""
# SPDX-License-Identifier: AGPL-3.0-or-later

from time import sleep as worker_sleep
import html

import orca
from .protocol import Path, json
from .service import HostService, SLICE_EVENTS

# %%BRIDGE_PROTOCOL%%
# %%BRIDGE_SERVICE%%


class RRSHostBridge(orca.script.ScriptPluginCapabilityBase):
    def get_name(self):
        return "RRS MCP local bridge"

    def get_default_config(self):
        return {"export_roots": []}

    def _message(self, message):
        if not self.stopping and (message or {}).get("command") == "tick":
            self.service.poll_ui()

    def execute(self):
        if getattr(self, "running", False):
            return orca.ExecutionResult.skipped("Bridge is already running")
        self.running = True
        self.stopping = False
        self.service = None
        self.window = None
        try:
            storage = Path(orca.host.plugin.storage()) / "rrs-mcp-bridge"
            config = json.loads(self.get_config())
            roots = config.get("export_roots", [])
            if not isinstance(roots, list) or any(
                not isinstance(p, str) or not Path(p).expanduser().is_absolute() for p in roots
            ):
                raise ValueError("export_roots must contain absolute directory paths")
            self.service = HostService(
                orca, storage, [storage / "exports"] + [Path(p) for p in roots]
            )
            self.service.heartbeat("starting")
            page = """<!doctype html><meta charset="utf-8"><title>RRS MCP Bridge</title>
              <style>body{font:15px system-ui;padding:20px;overflow-wrap:anywhere}code{display:block;padding:12px;background:#ddd;color:#222}button{padding:8px}</style>
              <h2>RRS MCP local bridge</h2><p>The bridge is active while this panel stays open.</p>
              <p>Set ORCA_MCP_BRIDGE in your MCP client to:</p><code>__STORE__</code>
              <p>Preset changes remain unsaved. Orca's native validation and unsaved-edit dialogs apply.</p>
              <p>Close this window to stop new requests. A started native transaction may still finish.</p>
              <script>setInterval(()=>{if(window.orca)orca.postMessage({command:'tick'});},250);</script>"""
            self.window = orca.host.ui.create_window(
                html=page.replace("__STORE__", html.escape(str(storage))),
                title="RRS MCP Bridge",
                width=650,
                height=430,
                on_message=self._message,
                on_close=lambda: setattr(self, "stopping", True),
            )
            while not self.stopping and self.window.is_open():
                self.service.poll_worker()
                worker_sleep(0.1)
            return orca.ExecutionResult.success("RRS MCP bridge stopped")
        finally:
            try:
                if self.service is not None:
                    self.service.close()
            finally:
                try:
                    if self.window is not None and self.window.is_open():
                        self.window.close()
                finally:
                    self.running = False

    def on_cancelled(self):
        self.stopping = True


if hasattr(getattr(orca, "slicing", None), "SlicingPipelineCapabilityBase"):

    class RRSSliceObserver(orca.slicing.SlicingPipelineCapabilityBase):
        def get_name(self):
            return "RRS MCP slicing observer"

        def execute(self, ctx):
            # Synchronous, no filesystem/UI/network access from the slicing thread.
            SLICE_EVENTS.observe(ctx)
            return orca.ExecutionResult.success()


@orca.plugin
class RRSBridgePackage(orca.base):
    def register_capabilities(self):
        orca.register_capability(RRSHostBridge)
        if "RRSSliceObserver" in globals():
            orca.register_capability(RRSSliceObserver)
