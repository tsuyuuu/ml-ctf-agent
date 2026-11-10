"""
solver_runtime.py - Isolated Docker Solver Environment

This module manages the Docker container used by our autonomous
CTF agent to execute commands and analyze challenge files.

The DockerSolver class is responsible for:
1. Creating an isolated, unprivileged Docker container.
2. Restricting network access, filesystem access, and system resources.
3. Mounting authorized contestant files as read-only.
4. Executing agent commands with enforced timeouts.
5. Stopping and removing the container after execution.

This separates the agent's command execution environment from the
trusted controller, which manages challenge metadata and evaluation.
"""
import subprocess
import uuid
from pathlib import Path

class DockerSolver:
     # Manage the lifecycle and command execution of a restricted Docker container.
    def __init__(self, image="ctf-solver:dev"):
        self.image = image
        self.container_id = None

    def start(self, challenge_dir=None):
        """Start a fresh, restricted solver container."""

        # Prevent multiple containers from being started by the same instance.
        if self.container_id is not None:
            raise RuntimeError("Solver already running")

        # Generate a unique container name to avoid naming conflicts.
        name = f"ctf-{uuid.uuid4().hex[:12]}"

        # Configure Docker isolation and resource restrictions.
        cmd = [
            "docker", "run", "-d", "--rm",
            "--name", name,
            
            # Disable container networking to prevent external access.
            "--network", "none",
            
            # Make the container's root filesystem read-only.
            "--read-only",

            # Remove Linux capabilities and prevent privilege escalation.
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",

             # Limit process count, memory consumption, and CPU usage.
            "--pids-limit", "64",
            "--memory", "512m",
            "--cpus", "1",

            # Run commands as an unprivileged user rather than root.
            "--user", "10001:10001",

            # Set the default working directory for agent commands.
            "--workdir", "/work",

            # Provide a writable, executable temporary workspace.
            # Restrict ownership to the unprivileged solver user.
            "--tmpfs",
            "/work:rw,exec,nosuid,nodev,uid=10001,gid=10001,mode=0700,size=64m",
            
            # Provide temporary storage for programs that require /tmp.
            "--tmpfs",
            "/tmp:rw,uid=10001,gid=10001,mode=1777,size=32m",
        ]

        # Mount authorized contestant files when a challenge is provided.
        if challenge_dir is not None:
            path = Path(challenge_dir).resolve()

            # Validate that the challenge directory exists.
            if not path.is_dir():
                raise ValueError("Challenge directory not found")

            # Mount challenge files read-only so the agent can inspect
            # them without modifying the original contestant files.
            cmd += [
                "--mount",
                f"type=bind,src={path},dst=/challenge,readonly"
            ]

        # Keep the container running so commands can be executed later.
        cmd += [self.image, "sleep", "infinity"]

        # Launch the container and capture its unique Docker ID.
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
            # Execute the command inside the existing container.
            # The Linux timeout utility limits command execution time.
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

            # Exit code 124 indicates that the timeout utility
            # terminated the command after exceeding its time limit.
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
            # Stop the container if the host-side subprocess
            # exceeds its timeout, preventing continued execution.
            self.stop()
            return {
                "error": "Command timeout; container terminated",
                "timed_out": True
            }

    def stop(self):
        """Destroy the solver container."""

        # Clear the stored ID and force-remove the container.
        if self.container_id:
            container_id = self.container_id
            self.container_id = None

            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                timeout=15,
                check=False
            )
