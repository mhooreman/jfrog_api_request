"""Run an jfrog API query, and print the result (see DESCRIPTION).

This script uses PIP configuration for JFrog, but is intended to be used
for debugging while JFrog has problems.

So it means that we can't rely on JFrog, and ONLY vanilla python can be used,
hence the use of curl as a backend.
"""

import argparse
import configparser
import dataclasses
import functools
import logging
import os
import pathlib
import platform
import pprint
import sys
import typing

from .exceptions import (
    AppDataNotSetError,
    CurlNotFoundError,
    MissingPipConfigFileOptionError,
    MissingPipConfigFileSectionError,
    PipConfigFileNotFoundError,
    RunHasNoError,
    SystemRootNotSetError,
    TAnyProcessingError,
    UnsupportedOperatingSystemError,
)
from .processors import CurlCommandProcessor, UrlProcessor

__version__: typing.Final[str] = "1.0.0"
DESCRIPTION: typing.Final[str] = (
    "Run a JFrog API query and print the result as evaluable python "
    "code (or text if not possible). JFrog URL and credentials are "
    "read from system PIP configuration."
)
_DEFAULT_ENTRYPOINT: typing.Final[str] = "/pypi/pypi/simple/"
_USER_AGENT: typing.Final[str] = (
    # This is the user agent of Microsoft Edge 142.0.3595.90
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
)


def _get_pip_configured_jfrog_url() -> str:
    """Return the JFrog URL configured in pip.

    :raises AppDataNotSetError: The APPDATA environment variable is not set
    :raises PipConfigFileNotFoundError: The PIP configuration file cannot be
        found
    :raises MissingPipConfigFileSectionError: A section is missing in the PIP
        configuration file
    :raises MissingPipConfigFileOptionError: An option is missing in the PIP
        configuration file, while the corresponding section exists
    :return: The URL, as provided in the configuration (e.g. not parsed)
    """
    parser = configparser.ConfigParser()
    section = "global"
    option = "index-url"
    try:
        appdata = os.environ["APPDATA"]
    except KeyError as e:
        raise AppDataNotSetError from e
    pip_config_path = pathlib.Path(appdata) / "pip" / "pip.ini"
    if not pip_config_path.exists():
        raise PipConfigFileNotFoundError(pip_config_path)

    with pip_config_path.open("r") as fp:
        parser.read_file(fp)
    try:
        ret = parser.get(section, option)
    except configparser.NoSectionError as e:
        raise MissingPipConfigFileSectionError(section) from e
    except configparser.NoOptionError as e:
        raise MissingPipConfigFileOptionError(section, option) from e

    return ret


@dataclasses.dataclass(kw_only=True, frozen=True)
class App:
    """Provide the main application.

    The application entry point is the static method `main` provided here.
    """

    apicall: str
    verbose: bool
    quiet: bool
    ssl: bool

    @functools.cached_property
    def logger(self) -> logging.Logger:
        """Provide the configured standard python logger.

        :raises ValueError: The application is set both in quiet and verbose
            mode
        :return: The logger
        """
        if self.verbose and self.quiet:
            msg = "Can't be both quiet and verbose"
            raise ValueError(msg)
        if self.verbose:
            lvl = logging.DEBUG
        elif self.quiet:
            lvl = logging.WARNING
        else:
            lvl = logging.INFO
        ret = logging.getLogger(pathlib.Path(__file__).stem)
        ret.setLevel(lvl)
        hdl = logging.StreamHandler()
        fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s"
        )
        hdl.setLevel(lvl)
        hdl.setFormatter(fmt)
        ret.addHandler(hdl)
        return ret

    @property
    def _curl_path(self) -> pathlib.Path:
        """Provide the curl application path.

        :raises SystemRootNotSetError:
            The ``SYSTEMROOT`` environment variable is not set
        :raises CurlNotFoundError: _description_
            The computed path does not exists
        :return: The computed path
        """
        try:
            sysroot = os.environ["SYSTEMROOT"]
        except KeyError as e:
            raise SystemRootNotSetError from e
        ret = pathlib.Path(sysroot) / "system32" / "curl.exe"
        if not ret.exists():
            raise CurlNotFoundError(ret)
        return ret

    @staticmethod
    def _ask_confirmation(msg: str, *, notty_value: bool = False) -> bool:
        """Ask a confirmation message.

        Allowed replies are Y or N (case insensitive). Any other provided
        reply will repeat the question. It means that there is no
        "default reply" and the user is obliged to enter a value.

        If not running on an interactive terminal, don't ask and return the
        provided notty value instead, which defaults to False: "If I can't
        guess, I consider that it is rejected".

        :param msg: The confirmation message, on which " [Y|N] " will be aded
        :param notty_reply: The reply to give while not running on an
            interactive termina, defaults to False
        :return: True or False if the case insensitive reply is Y or N
            respectively
        """
        msg += " [Y|N] "
        if not sys.stdin.isatty():
            return notty_value
        while True:
            reply = input(msg).strip().upper()
            if reply == "Y":
                return True
            if reply == "N":
                return False

    @functools.cached_property
    def processed_url(self) -> UrlProcessor:
        """Provide the processed target URL."""
        ret = UrlProcessor.from_url(
            _get_pip_configured_jfrog_url()
        ).get_new_updated_apicall(
            self.apicall
        )
        if not ret.path_ends_with_slash:
            msg = (
                "The entry point shall usually end with a / with this "
                "API. Shall I add it?"
            )
            if self._ask_confirmation(msg):
                ret = ret.get_new_add_slash_to_path()
        if not ret.path_ends_with_slash:
            # Need to redo the test as the situation might have changed
            self.logger.warning(
                "The URL %s does not ends with /, which is unusual",
                ret.url
            )
        return ret

    @functools.cached_property
    def _curl_command_line_and_stdin(self) -> tuple[list[str], str]:
        """Provide the curl command line.

        This provides a list suited for subprocess in a non-shell mode. In
        addition, it provides stdin to send to subprocess.Popen.communicate.

        The stdin contains the token, and we ask curl to read the config
        from stdin. It avoid to use a command line containg a secret token,
        which would be visibile using operating system process monitoring
        tools.
        """
        ret = [str(self._curl_path)]
        if not self.ssl:
            ret.append("--ssl-no-revoke")
        ret += [
            "--user",
            self.processed_url.username,
            "--password",
            # Giving empty password otherwize curl wait for additional input
            "",
            "--user-agent",
            _USER_AGENT,
            "--styled-output",
            self.processed_url.url_no_credentials,
            # Below: Needed even if not verbose because we process stdout
            "--verbose",
            "--header",
            "--errors",
            "--trace-time",
            "--config", "-"
        ]
        stdin = (
            'header = "Authorization: Bearer '
            f'{self.processed_url.token}"'
        )
        return ret, stdin

    @property
    def query_result(self) -> object:
        """Provide the result op the query.

        If the result is JSON, it returns the loaded value. Otherwize, it
        returns the text value or None.

        JSON identification is done the following way:
        - Based on the (case insensitive) content-type header
        - If that header is not available, trying to load JSON and falling
          back to text if the loading failed.
        """
        cmdline, stdin = self._curl_command_line_and_stdin
        return CurlCommandProcessor(
            logger=self.logger,
            cmdline=cmdline,
            stdin=stdin
        ).processed_output

    def __call__(self) -> None:
        """Execute the instance and exit reflecting the status.

        This is called from `self.main`.
        """
        try:
            if platform.system() != "Windows":
                raise UnsupportedOperatingSystemError
            res = self.query_result
            self.logger.info("Data shown to stdout")
            if isinstance(res, None | str):
                # We really want to print it, even if None
                print(res)  # noqa: T201
            else:
                pprint.pprint(res)  # noqa: T203
        except TAnyProcessingError as e:
            ex = e
        else:
            ex = RunHasNoError()
        ex.exit(self.logger)

    @classmethod
    def main(cls) -> None:
        """Execute the application.

        This is the entry point. It parses the command line, creates the
        instance and call it.
        """
        p = argparse.ArgumentParser(
            description=DESCRIPTION,
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
        cls(**vars(p.parse_args()))()


if __name__ == "__main__":
    App.main()
