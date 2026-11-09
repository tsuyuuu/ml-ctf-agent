
from solver_runtime import DockerSolver

solver = DockerSolver()

try:
    print("Starting solver...")
    solver.start()

    print("\nTest 1: Identity")
    print(solver.run_command("id"))

    print("\nTest 2: Tool availability")
    print(solver.run_command("which objdump"))

    print("\nTest 3: Persistent workspace")
    print(solver.run_command("echo hello > test.txt"))
    print(solver.run_command("cat test.txt"))

finally:
    solver.stop()
    print("\nSolver stopped.")
