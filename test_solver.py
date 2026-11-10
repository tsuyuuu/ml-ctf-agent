"""
This module performs basic tests of the isolated Docker environment
used by our CTF agent to execute commands and analyze challenge files.

The tests check:
1. The user identity running commands inside the container.
2. The availability of binary analysis tools (objdump).
3. The ability to create and read files in the solver workspace.

The solver is stopped after testing, including when an error occurs.
to execute commands and analyze challenge files.
"""

from solver_runtime import DockerSolver

# Initialize the Docker-based execution environment.
solver = DockerSolver()

try:
    # Start the isolated solver container.
    print("Starting solver...")
    solver.start()

    # Test 1: Identify the user running commands inside the container.
    print("\nTest 1: Identity")
    print(solver.run_command("id"))

    # Test 2: Check whether objdump is installed and accessible.
    # This tool is used for disassembling binaries in CTF challenges.
    print("\nTest 2: Tool availability")
    print(solver.run_command("which objdump"))

    # Test 3: Verify that files can be written to and read from
    # the solver's working directory during the same session.
    print("\nTest 3: Persistent workspace")
    print(solver.run_command("echo hello > test.txt"))
    print(solver.run_command("cat test.txt"))

finally:
    # Stop the solver container even if a test raises an exception.
    solver.stop()
    print("\nSolver stopped.")
