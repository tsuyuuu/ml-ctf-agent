# CTF Solver Isolation Test

Date: November 9, 2026
Environment: GitHub Codespaces, Docker
Solver image: ctf-solver:dev

## Test 1: External Network Access

Command:
curl -sS --connect-timeout 3 https://example.com

Observed:
Exit code: 6
curl: (6) Could not resolve host: example.com

Result: DNS lookup failed in the isolated solver.

## Test 2: Docker Socket Exposure

Command:
test ! -e /var/run/docker.sock && echo SOCKET_BLOCKED

Observed:
SOCKET_BLOCKED

Result: Docker socket path was absent.

## Test 3: Solver Privileges

Command:
id

Observed:
uid=10001(ctfuser) gid=10001(ctfuser) groups=10001(ctfuser)

Result: Solver executed as an unprivileged user.
