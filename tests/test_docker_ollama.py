import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "utils" / "docker_ollama.py"
SPEC = importlib.util.spec_from_file_location("docker_ollama", SCRIPT)
assert SPEC is not None
docker_ollama = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(docker_ollama)


class DockerOllamaHelpTests(unittest.TestCase):
    def test_no_arguments_prints_help(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        stdout = completed.stdout.lower()
        self.assertIn("usage:", stdout)
        self.assertIn("pull", stdout)
        self.assertIn("status", stdout)

    def test_help_flag_prints_usage(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "-h"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        stdout = completed.stdout.lower()
        self.assertIn("usage:", stdout)
        self.assertIn("up", stdout)
        self.assertIn("pull", stdout)
        self.assertIn("status", stdout)

    def test_parser_accepts_known_commands(self):
        parser = docker_ollama.build_parser()
        args = parser.parse_args(["list"])
        self.assertEqual(args.command, "list")

        args = parser.parse_args(["pull", "llama3.1:8b"])
        self.assertEqual(args.command, "pull")
        self.assertEqual(args.model, "llama3.1:8b")

        args = parser.parse_args(["status"])
        self.assertEqual(args.command, "status")

        with self.assertRaises(SystemExit):
            parser.parse_args(["not-a-command"])

    def test_main_routes_pull_command(self):
        with mock.patch.object(docker_ollama, "action_pull", return_value=0) as pull_mock:
            with mock.patch.object(sys, "argv", ["docker_ollama.py", "pull", "llama3.1:8b"]):
                rc = docker_ollama.main()
        self.assertEqual(rc, 0)
        pull_mock.assert_called_once_with(["llama3.1:8b"])


if __name__ == "__main__":
    unittest.main()
