
import subprocess
import uuid
from pathlib import Path


class DockerSolver:
    def __init__(self, image="ctf-solver:dev"):
        self.image = image
        self.container_id = None

    def start(self, challenge_dir=None):
        """Start a fresh, restricted solver container."""

        if self.container_id is not None:
            raise RuntimeError("Solver already running")

        name = f"ctf-{uuid.uuid4().hex[:12]}"

        cmd = [
            "docker", "run", "-d", "--rm",
            "--name", name,
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
            "--memory", "512m",
            "--cpus", "1",
            "--user", "10001:10001",
            "--workdir", "/work",
            "--tmpfs",
            "/work:rw,exec,nosuid,nodev,uid=10001,gid=10001,mode=0700,size=64m",
            "--tmpfs",
            "/tmp:rw,uid=10001,gid=10001,mode=1777,size=32m",
        ]

        if challenge_dir is not None:
            path = Path(challenge_dir).resolve()

            if not path.is_dir():
                raise ValueError("Challenge directory not found")

            # Only pass a prepared directory containing
            # contestant-facing files, never the benchmark repo.
            cmd += [
                "--mount",
                f"type=bind,src={path},dst=/challenge,readonly"
            ]

        cmd += [self.image, "sleep", "infinity"]

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=30, check=True
        )

        self.container_id = result.stdout.strip()
        return self.container_id

    def run_command(self, command, timeout_s=10):
        """Execute a command inside the solver container."""

        if not self.container_id:
            return {"error": "Solver not running"}

        if not isinstance(command, str) or not command.strip():
            return {"error": "Invalid command"}

        if len(command) > 4000:
            return {"error": "Command too long"}

        limit = max(1, min(10, int(timeout_s)))

        try:
            result = subprocess.run(
                [
                    "docker", "exec",
                    "--workdir", "/work",
                    self.container_id,
                    "timeout", "-k", "2",
                    f"{limit}s",
                    "sh", "-c", command
                ],
                capture_output=True,
                text=True,
                timeout=limit + 4
            )

            timed_out = result.returncode == 124

            output = {
                "exit_code": result.returncode,
                "stdout": result.stdout[:6000],
                "stderr": result.stderr[:1000],
                "truncated": len(result.stdout) > 6000,
                "timed_out": timed_out
            }

            if timed_out:
                self.stop()

            return output

        except subprocess.TimeoutExpired:
            self.stop()
            return {
                "error": "Command timeout; container terminated",
                "timed_out": True
            }

    def stop(self):
        """Destroy the solver container."""

        if self.container_id:
            container_id = self.container_id
            self.container_id = None

            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                timeout=15,
                check=False
            )
