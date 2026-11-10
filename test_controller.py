# Tests the ToolDispatcher: checks that each agent tool works correctly inside the Docker sandbox and that unsafe file access is blocked.

from solver_runtime import DockerSolver
from controller import ToolDispatcher

solver = DockerSolver()

try:
    solver.start()

    # Route the agent's tool calls (run_command, write_file, read_file) to the sandbox.
    tools = ToolDispatcher(solver)

    # Confirm shell commands run and Python is available.
    print("TEST 1: Execute command")
    print(tools("run_command", {
        "command": "python3 --version"
    }))

    # Confirm the agent can create files in its /work directory.
    print("\nTEST 2: Write file")
    print(tools("write_file", {
        "path": "example.py",
        "content": "print('Hello from the CTF solver!')"
    }))

    # Confirm a file the agent wrote can be executed.
    print("\nTEST 3: Execute created file")
    print(tools("run_command", {
        "command": "python3 /work/example.py"
    }))

    # Confirm the agent can read back files from /work.
    print("\nTEST 4: Read file")
    print(tools("read_file", {
        "path": "example.py"
    }))

    # Confirm reads outside the allowed directories are rejected.
    print("\nTEST 5: Block unauthorized path")
    print(tools("read_file", {
        "path": "/etc/passwd"
    }))

finally:
    solver.stop()
    print("\nSolver stopped.")
