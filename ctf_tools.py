import shlex


def inspect_binary(solver, path):
    """
    Inspect a contestant binary using bounded commands
    inside the isolated Docker solver.
    """

    if not isinstance(path, str):
        return {"error": "Path must be a string"}

    if not path.startswith(("/challenge/", "/work/")):
        return {"error": "Path outside allowed directories"}

    quoted = shlex.quote(path)

    commands = {
        "file_type": f"file {quoted}",
        "elf_header": (
            f"readelf -h {quoted} 2>/dev/null | head -35"
        ),
        "interesting_strings": (
            f"strings -a {quoted} | "
            "grep -Ei 'flag|password|correct|wrong|"
            "error|success|denied|input|usage' | head -30"
        ),
    }

    results = {}

    for name, command in commands.items():
        result = solver.run_command(command, timeout_s=10)
        results[name] = {
            "output": result.get("stdout", "")[:2000],
            "error": result.get("stderr", "")[:300],
            "exit_code": result.get("exit_code"),
        }

    return results
