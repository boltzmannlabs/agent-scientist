"""Long requested terminal timeouts stay in the foreground and execute once."""
import json
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Shared test config dict — mirrors _get_env_config() return shape.
# ---------------------------------------------------------------------------
def _make_env_config(**overrides):
    """Return a minimal _get_env_config()-shaped dict with optional overrides."""
    config = {
        "env_type": "local",
        "timeout": 180,
        "cwd": "/tmp",
        "host_cwd": None,
        "modal_mode": "auto",
        "docker_image": "",
        "singularity_image": "",
        "modal_image": "",
        "daytona_image": "",
    }
    config.update(overrides)
    return config

class TestForegroundTimeout:
    """Requested deadlines never silently change execution mode."""

    def test_long_foreground_command_completes_without_spawning_background(self, tmp_path, monkeypatch):
        from tools.terminal_tool import terminal_tool

        monkeypatch.setenv("SCI_HOME", str(tmp_path / "sci"))
        marker = tmp_path / "ran"
        with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config(cwd=str(tmp_path))), \
             patch("tools.terminal_tool._start_cleanup_thread"), \
             patch("tools.terminal_tool.spawn_background_process", side_effect=AssertionError("Unexpected handoff")), \
             patch("tools.terminal_tool._check_all_guards", return_value={"approved": True}):
            result = json.loads(terminal_tool(command=f"echo x >> {marker}", timeout=9999))

        assert result.get("error") is None
        assert result["exit_code"] == 0
        assert "session_id" not in result and "promoted_from_foreground" not in result
        assert marker.read_text().count("x") == 1

    def test_zero_timeout_rejected(self):
        """timeout=0 must be rejected, not silently coerced to the default."""
        from tools.terminal_tool import terminal_tool

        with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config()), \
             patch("tools.terminal_tool._start_cleanup_thread"):
            result = json.loads(terminal_tool(command="echo hi", timeout=0))

        assert result.get("error")
        assert "positive" in result["error"]

    def test_negative_timeout_rejected(self):
        """timeout=-1 must be rejected, not fire an immediate '-1s' timeout."""
        from tools.terminal_tool import terminal_tool

        with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config()), \
             patch("tools.terminal_tool._start_cleanup_thread"):
            result = json.loads(terminal_tool(command="echo hi", timeout=-1))

        assert result.get("error")
        assert "positive" in result["error"]

    def test_foreground_allows_help_variant_for_server_command(self):
        """Informational variants like '--help' should not be blocked."""
        from tools.terminal_tool import terminal_tool

        with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config()), \
             patch("tools.terminal_tool._start_cleanup_thread"):

            mock_env = MagicMock()
            mock_env.execute.return_value = {"output": "usage", "returncode": 0}

            with patch("tools.terminal_tool._active_environments", {"default": mock_env}), \
                 patch("tools.terminal_tool._last_activity", {"default": 0}), \
                 patch("tools.terminal_tool._check_all_guards", return_value={"approved": True}):
                result = json.loads(terminal_tool(command="pnpm dev --help"))

        assert result["error"] is None
        call_kwargs = mock_env.execute.call_args
        assert call_kwargs[0][0] == "pnpm dev --help"

    def test_config_default_above_cap_not_rejected(self):
        """When config default timeout > cap but model passes no timeout, execute normally.

        Only the model's explicit timeout parameter triggers rejection,
        not the user's configured default.
        """
        from tools.terminal_tool import terminal_tool

        # User configured TERMINAL_TIMEOUT=900 in their env
        with patch("tools.terminal_tool._get_env_config",
                    return_value=_make_env_config(timeout=900)), \
             patch("tools.terminal_tool._start_cleanup_thread"):

            mock_env = MagicMock()
            mock_env.execute.return_value = {"output": "done", "returncode": 0}

            with patch("tools.terminal_tool._active_environments", {"default": mock_env}), \
                 patch("tools.terminal_tool._last_activity", {"default": 0}), \
                 patch("tools.terminal_tool._check_all_guards", return_value={"approved": True}):
                result = json.loads(terminal_tool(command="make build"))

        # Should execute with the config default, NOT be rejected
        call_kwargs = mock_env.execute.call_args
        assert call_kwargs[1]["timeout"] == 900
        assert "error" not in result or result["error"] is None

    def test_exactly_at_max_not_rejected(self):
        """Timeout exactly at 600 should execute normally."""
        from tools.terminal_tool import terminal_tool

        with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config()), \
             patch("tools.terminal_tool._start_cleanup_thread"):

            mock_env = MagicMock()
            mock_env.execute.return_value = {"output": "done", "returncode": 0}

            with patch("tools.terminal_tool._active_environments", {"default": mock_env}), \
                 patch("tools.terminal_tool._last_activity", {"default": 0}), \
                 patch("tools.terminal_tool._check_all_guards", return_value={"approved": True}):
                result = json.loads(terminal_tool(
                    command="echo hello",
                    timeout=600,  # Exactly at limit
                ))

        call_kwargs = mock_env.execute.call_args
        assert call_kwargs[1]["timeout"] == 600
        assert "error" not in result or result["error"] is None

class TestDetachmentGuard:
    def test_over_cap_timeout_with_shell_backgrounding_is_still_refused(self):
        """Independent-review witness: a promoted `cmd &` started a tracked shell that exited at once
        while the payload ran untracked, defeating the guidance the refusal exists for."""
        from tools.terminal_tool import terminal_tool

        with patch("tools.terminal_tool._get_env_config", return_value=_make_env_config()), \
             patch("tools.terminal_tool._start_cleanup_thread"):
            result = json.loads(terminal_tool(command="sleep 5 &", timeout=9999))
            result2 = json.loads(terminal_tool(command="nohup make test", timeout=9999))
        assert "'&' backgrounding" in result["error"]
        assert "nohup" in result2["error"]
