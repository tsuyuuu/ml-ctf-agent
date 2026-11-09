
from solver_runtime import DockerSolver
from controller import ToolDispatcher

solver = DockerSolver()

try:
    solver.start()
    tools = ToolDispatcher(solver)

    print("TEST 1: Execute command")
    print(tools("run_command", {
        "command": "python3 --version"
    }))

    print("\nTEST 2: Write file")
    print(tools("write_file", {
        "path": "example.py",
        "content": "print('Hello from the CTF solver!')"
    }))

    print("\nTEST 3: Execute created file")
    print(tools("run_command", {
        "command": "python3 /work/example.py"
    }))

    print("\nTEST 4: Read file")
    print(tools("read_file", {
        "path": "example.py"
    }))

    print("\nTEST 5: Block unauthorized path")
    print(tools("read_file", {
        "path": "/etc/passwd"
    }))

finally:
    solver.stop()
    print("\nSolver stopped.")
