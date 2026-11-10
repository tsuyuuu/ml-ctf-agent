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


def disassemble_binary(solver, path, start_address, stop_address):
    """
    Return bounded Intel-syntax disassembly from a binary.

    Addresses must be hexadecimal strings, e.g. 0x400f10.
    The maximum allowed address range is 512 bytes.
    """
    import re

    if not all(isinstance(x, str) for x in (
        path, start_address, stop_address
    )):
        return {"error": "Arguments must be strings"}

    if not re.fullmatch(r"0x[0-9a-fA-F]+", start_address):
        return {"error": "Invalid start address"}

    if not re.fullmatch(r"0x[0-9a-fA-F]+", stop_address):
        return {"error": "Invalid stop address"}

    start = int(start_address, 16)
    stop = int(stop_address, 16)

    if start >= stop:
        return {"error": "Stop address must exceed start address"}

    if stop - start > 512:
        return {"error": "Address range exceeds 512 bytes"}

    quoted = shlex.quote(path)

    command = (
        f"objdump -d -M intel "
        f"--start-address={start} "
        f"--stop-address={stop} "
        f"{quoted}"
    )

    result = solver.run_command(command, timeout_s=10)

    output = result.get("stdout", "")

    return {
        "disassembly": output[:5000],
        "truncated": len(output) > 5000,
        "exit_code": result.get("exit_code"),
        "error": result.get("stderr", "")[:500],
    }

