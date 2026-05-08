"""Command line interface manaement."""

import argparse
import os
import pathlib
import typing

from . import __version__

_DEFAULT_ENTRYPOINT: typing.Final[str] = "/pypi/pypi/simple/"
_DESCRIPTION: typing.Final[str] = (
    "Run a JFrog API query and print the result as evaluable python "
    "code (or text if not possible). JFrog URL and credentials are "
    "read from system PIP configuration."
)


def _existing_readable_path(val: str) -> pathlib.Path:
    """Convert a path string to a readable path object.

    :param val: The path string
    :raises argparse.ArgumentTypeError: The path does not exist or is not
        readable (will be managed as a command line error)
    :return: The path
    """
    ret = pathlib.Path(val)
    if not ret.exists():
        msg = f"{ret} does not exist"
        raise argparse.ArgumentTypeError(msg)
    if not os.access(ret, os.R_OK):
        msg = f"{ret} is not readable"
        raise argparse.ArgumentTypeError(msg)
    return ret


def _existing_executable_path(val: str) -> pathlib.Path:
    """Convert a path string to an executable path object.

    This first ensures that this is an existing reable path, and then cheks
    that this can be executed.

    :param val: The path string
    :raises argparse.ArgumentTypeError: The path does not exist or is not
        readable or is not executable (will be managed as a command line error)
    :return: The path
    """
    ret = _existing_readable_path(val)
    if not os.access(ret, os.X_OK):
        msg = f"{ret} is not executable"
        raise argparse.ArgumentTypeError(msg)
    return ret


def parse() -> argparse.Namespace:
    """Parse the command line arguments.

    :return: Result of argparse's parse_args
    """
    p = argparse.ArgumentParser(
        description=_DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    p.add_argument(
        "-a",
        "--apicall",
        default=_DEFAULT_ENTRYPOINT,
        required=False,
        help="the api call (the url after /app + query params if any)",
    )
    qv = p.add_mutually_exclusive_group()
    qv.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="do now show log info",
    )
    qv.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="show log debug and detailed curl run",
    )
    p.add_argument(
        "-s",
        "--ssl",
        action="store_true",
        default=False,
        help="ask curl to perform SSL revocation check",
    )
    p.add_argument(
        "--pip-config",
        dest="provided_pip_config_path",
        metavar="PATH_TO_PIP_CONFIG",
        type=_existing_readable_path,
        required=False,
        default=None,
        help="the pip configuration file (guessed if not provided)"
    )
    p.add_argument(
        "--curl",
        dest="provided_curl_path",
        metavar="PATH_TO_CURL_BINARY",
        type=_existing_executable_path,
        required=False,
        default=None,
        help="the curl executable file (guessed if not provided)"
    )
    return p.parse_args()
