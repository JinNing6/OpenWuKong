import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from openwukong.control.session_discovery import DiscoveredControlTarget
from openwukong.evaluation.session_registry_report import (
    StaticRegistryObserver,
    load_registry_states,
    main,
    run_session_registry_report,
)
from openwukong.monitor.ai_monitor import AIProjectState, AIStatus


def _state(
    *,
    pid: int,
    process_name: str,
    project_name: str,
    window_title: str,
) -> AIProjectState:
    return AIProjectState(
        timestamp=1.0,
        pid=pid,
        process_name=process_name,
        project_name=project_name,
        window_title=window_title,
        ai_status=AIStatus.UNKNOWN,
        ai_model="",
        agent_enabled=False,
        progress_text="",
        progress_pct=-1.0,
        last_ai_output="",
        ai_element_count=0,
    )


def _write_process_broker_store(
    path: Path,
    *,
    process_id: str,
    cwd: str,
    ownership_source: str = "test-store",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "mode": "command-intelligence-process-store",
                "safety_mode": "workspace_process_registry",
                "process_count": 1,
                "processes": [
                    {
                        "process_id": process_id,
                        "pid": os.getpid(),
                        "argv": ["python.exe", "-m", "http.server", "8765"],
                        "cwd": cwd,
                        "reason": "background dev server",
                        "effects": ["network"],
                        "env_keys": [],
                        "ownership": {
                            "owned": True,
                            "ownership_source": ownership_source,
                            "route_id": "terminal-native-session",
                            "connector_id": "terminal",
                            "workspace_root": cwd,
                            "cleanup_ready": True,
                        },
                        "started_at": 123.0,
                        "restored": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class _FakeSessionDiscovery:
    def __init__(self):
        self.calls = []

    def enrich(self, target):
        self.calls.append(target)
        return DiscoveredControlTarget(
            source=target,
            debugger_url="http://127.0.0.1:9237",
            resource_url=getattr(target, "resource_url", ""),
            evidence=(
                {
                    "kind": "browser_devtools",
                    "url": "http://127.0.0.1:9237",
                    "target_title": "Example",
                },
            ),
        )


class _ExplodingObserver:
    def snapshot(self):
        raise AssertionError("desktop observer must not run in broker-only mode")


class SessionRegistryReportTests(unittest.TestCase):
    def test_report_from_static_observer_is_read_only(self):
        observer = StaticRegistryObserver(
            [
                _state(
                    pid=101,
                    process_name="chrome.exe",
                    project_name="Example",
                    window_title="Example - Google Chrome",
                ),
                _state(
                    pid=102,
                    process_name="cursor.exe",
                    project_name="openwukong",
                    window_title="openwukong - Cursor",
                ),
            ]
        )

        report = run_session_registry_report(observer=observer)
        data = report.to_dict()

        self.assertEqual(data["mode"], "session-registry-report")
        self.assertEqual(data["safety_mode"], "read_only")
        self.assertFalse(data["control_allowed"])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["observed_state_count"], 2)
        self.assertEqual(data["registry"]["session_count"], 2)
        self.assertEqual(data["registry"]["app_family_counts"], {"browser": 1, "ide": 1})

    def test_cli_outputs_json_and_can_write_report_file(self):
        observer = StaticRegistryObserver(
            [
                _state(
                    pid=201,
                    process_name="pwsh.exe",
                    project_name="openwukong",
                    window_title="openwukong - PowerShell",
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "registry.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["--json", "--output", str(output)],
                    observer=observer,
                )

            printed = json.loads(stdout.getvalue())
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["mode"], "session-registry-report")
        self.assertEqual(written["registry"]["session_count"], 1)
        self.assertEqual(
            written["registry"]["sessions"][0]["preferred_route"],
            "terminal-native-session",
        )

    def test_cli_can_load_recorded_states_file(self):
        fixture = {
            "states": [
                {
                    "timestamp": 1.0,
                    "pid": 301,
                    "process_name": "chrome.exe",
                    "project_name": "Example",
                    "window_title": "Example - Google Chrome",
                    "resource_url": "https://example.test/",
                },
                {
                    "timestamp": 1.0,
                    "pid": 302,
                    "process_name": "notepad.exe",
                    "project_name": "notes",
                    "window_title": "notes.txt - Notepad",
                    "element_count": 3,
                    "semantic_input_count": 1,
                    "semantic_action_count": 1,
                    "input_candidate_count": 1,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "states.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")

            loaded = load_registry_states(path)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--states", str(path), "--json"])

        data = json.loads(stdout.getvalue())
        self.assertEqual(len(loaded), 2)
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["observed_state_count"], 2)
        self.assertEqual(data["registry"]["app_family_counts"]["browser"], 1)
        self.assertEqual(data["registry"]["app_family_counts"]["generic-desktop"], 1)

    def test_cli_can_discover_sessions_before_registry_registration(self):
        observer = StaticRegistryObserver(
            [
                _state(
                    pid=401,
                    process_name="chrome.exe",
                    project_name="Example",
                    window_title="Example - Google Chrome",
                )
            ]
        )
        discovery = _FakeSessionDiscovery()

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                ["--discover-sessions", "--json"],
                observer=observer,
                session_discovery=discovery,
            )

        data = json.loads(stdout.getvalue())
        session = data["registry"]["sessions"][0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(discovery.calls), 1)
        self.assertEqual(session["target"]["debugger_url"], "http://127.0.0.1:9237")
        self.assertIn("browser_devtools", session["capability_ids"])
        self.assertEqual(
            session["session_discovery"]["discovered_fields"]["debugger_url"],
            "http://127.0.0.1:9237",
        )

    def test_cli_binds_readiness_manifest_ownership_to_report_sessions(self):
        observer = StaticRegistryObserver(
            [
                _state(
                    pid=501,
                    process_name="chrome.exe",
                    project_name="Example",
                    window_title="Example - Google Chrome",
                )
            ]
        )
        discovery = _FakeSessionDiscovery()

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "browser.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mode": "session-readiness-execution",
                        "safety_mode": "isolated_helper_launch",
                        "launches": [
                            {
                                "action_id": "launch_browser_devtools_isolated",
                                "route_id": "browser-devtools-or-extension",
                                "connector_id": "browser",
                                "status": "started",
                                "pid": 7777,
                                "readiness_url": "http://127.0.0.1:9237",
                                "argv": [
                                    "chrome.exe",
                                    "--remote-debugging-port=9237",
                                    "--user-data-dir=E:/tmp/profile",
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--discover-sessions",
                        "--readiness-manifest",
                        str(manifest),
                        "--json",
                    ],
                    observer=observer,
                    session_discovery=discovery,
                )

        data = json.loads(stdout.getvalue())
        ownership = data["registry"]["sessions"][0]["ownership"]

        self.assertEqual(exit_code, 0)
        self.assertTrue(ownership["owned"])
        self.assertEqual(ownership["pid"], 7777)
        self.assertEqual(ownership["endpoint"], "http://127.0.0.1:9237")
        self.assertEqual(data["registry"]["ownership_counts"], {"owned": 1, "unowned": 0})

    def test_cli_can_include_process_broker_snapshot_file(self):
        broker_snapshot = {
            "mode": "command-process-broker-snapshot",
            "safety_mode": "read_only",
            "control_allowed": False,
            "control_attempts": 0,
            "active_count": 1,
            "stale_count": 0,
            "processes": [
                {
                    "process_id": "proc-1",
                    "pid": 6789,
                    "argv": ["python.exe", "-m", "http.server", "8765"],
                    "cwd": "E:/ideaProjects/agent/openwukong",
                    "running": True,
                    "exit_code": None,
                    "started_at": 123.0,
                    "restored": False,
                    "reason": "background dev server",
                    "effects": ["network"],
                    "ownership": {
                        "owned": True,
                        "ownership_source": "test",
                        "route_id": "terminal-native-session",
                        "connector_id": "terminal",
                        "workspace_root": "E:/ideaProjects/agent/openwukong",
                    },
                }
            ],
            "stale_processes": [],
            "broker": {
                "workspace_root": "E:/ideaProjects/agent/openwukong",
                "storage_path": "E:/ideaProjects/agent/openwukong/logs/runtime/processes.json",
                "profile_id": "network-enabled",
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broker_snapshot.json"
            path.write_text(json.dumps(broker_snapshot), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["--process-broker-snapshot", str(path), "--json"],
                    observer=StaticRegistryObserver([]),
                )

        data = json.loads(stdout.getvalue())
        session = data["registry"]["sessions"][0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["observed_state_count"], 0)
        self.assertEqual(data["registry"]["session_count"], 1)
        self.assertEqual(data["registry"]["app_family_counts"], {"managed-process": 1})
        self.assertEqual(session["preferred_route"], "command-process-broker")
        self.assertEqual(session["target"]["session_id"], "command-process:proc-1")
        self.assertIn("stop_process", session["action_ids"])
        self.assertTrue(session["ownership"]["owned"])

    def test_cli_can_include_process_broker_storage_file_without_snapshot_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / "processes.json"
            _write_process_broker_store(
                storage,
                process_id="proc-storage",
                cwd=tmp,
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["--process-broker-storage", str(storage), "--json"],
                    observer=StaticRegistryObserver([]),
                )

        data = json.loads(stdout.getvalue())
        session = data["registry"]["sessions"][0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["observed_state_count"], 0)
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["registry"]["session_count"], 1)
        self.assertEqual(session["target"]["session_id"], "command-process:proc-storage")
        self.assertEqual(session["preferred_route"], "command-process-broker")
        self.assertEqual(
            session["session_discovery"]["discovered_fields"]["broker_storage_path"],
            str(storage),
        )
        self.assertTrue(session["ownership"]["owned"])

    def test_cli_can_discover_default_process_broker_storage_under_workspace_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            storage = root / "logs" / "runtime" / "supervisor-command-processes.json"
            _write_process_broker_store(
                storage,
                process_id="proc-discovered",
                cwd=str(root),
                ownership_source="default-discovery",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--discover-process-brokers",
                        "--workspace-root",
                        str(root),
                        "--json",
                    ],
                    observer=StaticRegistryObserver([]),
                )

        data = json.loads(stdout.getvalue())
        session = data["registry"]["sessions"][0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["registry"]["session_count"], 1)
        self.assertEqual(session["target"]["session_id"], "command-process:proc-discovered")
        self.assertEqual(session["ownership"]["ownership_source"], "default-discovery")
        self.assertEqual(data["registry"]["preferred_route_counts"], {"command-process-broker": 1})

    def test_cli_broker_only_mode_skips_desktop_observer_and_exports_broker_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / "processes.json"
            _write_process_broker_store(
                storage,
                process_id="proc-broker-only",
                cwd=tmp,
                ownership_source="broker-only",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--broker-only",
                        "--process-broker-storage",
                        str(storage),
                        "--json",
                    ],
                    observer=_ExplodingObserver(),
                )

        data = json.loads(stdout.getvalue())
        session = data["registry"]["sessions"][0]

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["observed_state_count"], 0)
        self.assertEqual(data["observed_states"], [])
        self.assertEqual(data["control_attempts"], 0)
        self.assertEqual(data["registry"]["session_count"], 1)
        self.assertEqual(session["target"]["session_id"], "command-process:proc-broker-only")
        self.assertEqual(session["ownership"]["ownership_source"], "broker-only")


if __name__ == "__main__":
    unittest.main()
