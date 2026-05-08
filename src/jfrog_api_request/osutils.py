"""OS dependent stuffs."""

import enum
import functools
import os
import pathlib
import platform

from .exceptions import (
    AppDataNotSetError,
    CurlNotFoundError,
    MissedOperatingSystemCaseError,
    PipConfigFileNotFoundError,
    SystemRootNotSetError,
    UnsupportedOperatingSystemError,
)


class SupportedOS(enum.Enum):
    """Enumeration of supported operating systems."""

    LINUX = enum.auto()
    MACOS = enum.auto()
    WINDOWS = enum.auto()


@functools.lru_cache(maxsize=1)
def detect_os() -> SupportedOS:
    """Return the operating system if supported.

    :raises UnsupportedOperatingSystemError: The OS is not supported.
    :return: The corresponding `SuportedOS` value
    """
    match platform.system():
        case "Linux":
            return SupportedOS.LINUX
        case "Darwin":
            return SupportedOS.MACOS
        case "Windows":
            return SupportedOS.WINDOWS
        case _:
            raise UnsupportedOperatingSystemError


def get_curl_path() -> pathlib.Path:
    """Return the location of curl.

    - On Windows, it is searching for %SYTEMROOT%/system32/curl.exe.
    - On Linux and MacOS, it is earching for curl in the standard binary
      directories including the ones within the user directory.

    :raises SystemRootNotSetError: The environment variable SYSTEMROOT is not
        set (only applicable if running on Windows)
    :raises CurlNotFoundError: We have not found curl on the potential standard
        locations.
    :raises MissedOperatingSystemCaseError: The implementation forgots the
        current operating system (programming error)
    :return: The path of curl
    """
    match detect_os():
        case SupportedOS.LINUX | SupportedOS.MACOS:
            ret: tuple[str, ...]
            ret = (
                "~/bin",
                "~/.bin",
                "~/.local/bin",
                "/usr/local/bin",
                "/opt/homebrew/bin",  # Will be dropped later on if on Linux
                "/opt/local/bin",
                "/usr/bin",
                "/bin",
            )
            if detect_os() == SupportedOS.LINUX:
                ret = tuple(r for r in ret if "homebrew" not in r.lower())
            parents = tuple(pathlib.Path(r).expanduser() for r in ret)
            binname = "curl"
        case SupportedOS.WINDOWS:
            try:
                sysroot = os.environ["SYSTEMROOT"]
            except KeyError as e:
                raise SystemRootNotSetError from e
            parents = (pathlib.Path(sysroot) / "system32", )
            binname = "curl.exe"
        case _:
            raise MissedOperatingSystemCaseError
    for parent in parents:
        path = parent / binname
        if path.exists():
            return path
    raise CurlNotFoundError


def get_pip_config_path() -> pathlib.Path:
    """Return the standard location of the pip configuration file.

    :raises AppDataNotSetError: The APPDATA environment variable is not set
        (only applicable if running on Windows)
    :raises PipConfigFileNotFoundError: The expected file does not exists
    :raises MissedOperatingSystemCaseError: The implementation forgots the
        current operating system (programming error)
    :raises RuntimeError: _description_
    :return: _description_
    """
    ret: pathlib.Path | None = None
    match detect_os():
        case SupportedOS.WINDOWS:
            try:
                appdata = os.environ["APPDATA"]
            except KeyError as e:
                raise AppDataNotSetError from e
            ret = pathlib.Path(appdata) / "pip" / "pip.ini"
            if not ret.exists():
                raise PipConfigFileNotFoundError
            return ret
        case SupportedOS.LINUX | SupportedOS.MACOS:
            cases = []
            if detect_os() == SupportedOS.MACOS:
                cases.append("~/Library/Application Support/pip/pip.conf")
            cases.append("~/.config/pip/pip.conf")
            for case in cases:
                p_case = pathlib.Path(case).expanduser()
                if p_case.exists():
                    return p_case
            raise PipConfigFileNotFoundError
        case _:
            raise MissedOperatingSystemCaseError
