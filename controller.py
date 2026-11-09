
import base64
import shlex
from pathlib import PurePosixPath


class ToolDispatcher:
    def __init__(self, solver):
        self.solver = solver

    def _safe_path(self, raw_path, write=False):
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError("Invalid path")

        if "\x00" in raw_path:
            raise ValueError("Invalid path")

        path = PurePosixPath(raw_path)

        if ".." in path.parts:
            raise ValueError("Parent directory traversal blocked")

        if not path.is_absolute():
            path = PurePosixPath("/work") / path

        value = str(path)

        if write:
            allowed = value.startswith("/work/")
        else:
            allowed = (
                value.startswith("/work/")
                or value.startswith("/challenge/")
            )

        if not allowed:
            raise ValueError("Path outside permitted workspace")

        return value

    def __call__(self, name, args, timeout_s=10):
        try:
            if name == "run_command":
                command = args["command"]

                return self.solver.run_command(
                    command, timeout_s=timeout_s
                )

            elif name == "read_file":
                path = self._safe_path(args["path"])

                command = (
                    "head -c 6001 -- "
                    + shlex.quote(path)
                )

                result = self.solver.run_command(
                    command, timeout_s=timeout_s
                )

                output = result.get("stdout", "")

                return {
                    "content": output[:6000],
                    "truncated": len(output) > 6000,
                    "exit_code": result.get("exit_code"),
                    "error": result.get("stderr", "")
                }

            elif name == "write_file":
                path = self._safe_path(
                    args["path"], write=True
                )

                content = args["content"]

                if not isinstance(content, str):
                    return {"error": "Content must be text"}

                # Keep requests bounded for this first version
                if len(content.encode("utf-8")) > 2000:
                    return {"error": "Content exceeds 2000 bytes"}

                encoded = base64.b64encode(
                    content.encode("utf-8")
                ).decode("ascii")

                command = (
                    "printf %s "
                    + shlex.quote(encoded)
                    + " | base64 -d > "
                    + shlex.quote(path)
                )

                result = self.solver.run_command(
                    command, timeout_s=timeout_s
                )

                return {
                    "written": result.get("exit_code") == 0,
                    "path": path,
                    "error": result.get("stderr", "")
                }

            elif name == "submit_flag":
                # Must connect to the private course
                # evaluator before real challenge runs.
                return {
                    "verified": False,
                    "error": "Evaluator not connected"
                }

            elif name == "finish":
                return {
                    "finished": True,
                    "reason": args.get("reason", "")
                }

            return {"error": "Unknown tool"}

        except (ValueError, KeyError, TypeError) as e:
            return {"error": str(e)}
