from __future__ import annotations

import subprocess


class KeychainPasswordError(RuntimeError):
    pass


def load_keychain_password(service: str, account: str) -> str:
    """Read one password without placing it in arguments, logs, or Git."""
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise KeychainPasswordError("macOS Keychain is unavailable") from error
    password = result.stdout.rstrip("\r\n")
    if result.returncode != 0 or not password:
        raise KeychainPasswordError(
            f"Database password was not found in Keychain for service {service!r} "
            f"and account {account!r}"
        )
    return password
