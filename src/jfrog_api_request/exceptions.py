"""Provide the custom exceptions."""

import enum
import platform
import typing

if typing.TYPE_CHECKING:
    import logging
    import subprocess


class MissedOperatingSystemCaseError(RuntimeError):
    """Method called from an OS not implemented in the function.

    This shows most probably a programming error.
    """

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__(platform.system())


class _ExitCodes(enum.Enum):
    """Exit codes used by _BasedProcessingError based exceptions."""

    SUCCESS = 0
    # Starting at 10 to avoid conflict with python interpreter, argparse, etc.
    UNSUPPORTED_OPERATING_SYSTEM = 10
    APPDATA_NOT_SET = enum.auto()
    SYSTEM_ROOT_NOT_SET = enum.auto()
    PIP_CONFIG_FILE_NOT_FOUND = enum.auto()
    MISSING_PIP_CONFIG_SECTION = enum.auto()
    MISSING_PIP_CONFIG_OPTION = enum.auto()
    FAILED_PARSING_CONFIGURED_JFROG_URL = enum.auto()
    CURL_FAILED = enum.auto()
    CURL_NOT_FOUND_ERROR = enum.auto()


class _BaseProcessingError(Exception):
    """Base class for Exceptions during application execution."""

    def __init__(
        self,
        exitcode: _ExitCodes,
        log_msg: str | None,
        log_args: tuple[object] | list[object] | None
    ) -> None:
        """Initialize the instance.

        :param exitcode: The exit status used when terminating due to this.
        :param log_msg: The log message, can include syslog placeholders
        :param log_args: The values for the placeholder in log_msg
        """
        self.exitcode = exitcode
        self.log_msg = log_msg
        self.log_args = log_args

    def show_log(self, logger: logging.Logger, *, for_exit: bool) -> None:
        """Show the corresponding log message.

        If the exit code is > O, that's en error message; otherwize that's
        a debug message.

        If the message is None and for_exit is None, nothing is shown.

        :param logger: The standard python logger to use
        :param for_exit: If True, message tells that it will exit and show
            the exit code as well as its enum label
        :raises RuntimeError: When the message is None and there are args
        """
        msg: str | None
        msg = "Exit with status %d (%s)" if for_exit else ""
        if self.log_msg is not None:
            msg += ": " + self.log_msg
        args = self.log_args
        if args is not None and msg is None:
            emsg = "args must be None when msg is None"
            raise RuntimeError(emsg)
        args = [self.exitcode.value, self.exitcode.name] if for_exit else []
        if self.log_args is not None:
            args += list(self.log_args)
        if msg is not None:
            msg = msg.strip()
        if msg:  # not empty string, not None
            f = logger.error if self.exitcode.value else logger.debug
            f(msg, *args)

    def exit(self, logger: logging.Logger) -> None:
        """Exit the application.

        It shows the log messages and exit with the exitcode.

        :param logger: The standard python logger to use
        :raises SystemExit: Raised to exit the python interpreter
        """
        self.show_log(logger=logger, for_exit=True)
        raise SystemExit(self.exitcode.value) from self


class ProblemWhileRunningCurlError(_BaseProcessingError):
    """We've got a problem while running curl."""

    def __init__(
            self, called_process_error: subprocess.CalledProcessError
        ) -> None:
        """Initialize the instance.

        :param called_process_error: The corresponding called process error
            object
        """
        self.called_process_error = called_process_error
        super().__init__(
            exitcode=_ExitCodes.CURL_FAILED,
            log_msg="Problem while running curl: %s",
            log_args=[str(self.called_process_error)]
        )


class UnsupportedOperatingSystemError(_BaseProcessingError):
    """The current operating system is not supported."""

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__(
            exitcode=_ExitCodes.UNSUPPORTED_OPERATING_SYSTEM,
            log_msg="Unsupported operating system %s, expecting Windows.",
            log_args=[platform.system()]
        )


class AppDataNotSetError(_BaseProcessingError):
    """The APPDATA environment variable is not set."""

    def __init__(self) -> None:
        """Initialize the instance."""
        msg = (
            "Cannot determine roaming application data location: "
            "environment variable ``APPDATA`` not set."
        )
        super().__init__(
            exitcode=_ExitCodes.APPDATA_NOT_SET,
            log_msg=msg,
            log_args=None
        )


class SystemRootNotSetError(_BaseProcessingError):
    """The SYSTEMROOT environment variable is not set."""

    def __init__(self) -> None:
        """Initialize the instance."""
        msg = (
            "Cannot determine windows's system room location: "
            "environment variable ``SYSTEMROOT`` not set."
        )
        super().__init__(
            exitcode=_ExitCodes.SYSTEM_ROOT_NOT_SET,
            log_msg=msg,
            log_args=None
        )


class CurlNotFoundError(_BaseProcessingError):
    """The curl binary path cannot be found."""

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__(
            exitcode=_ExitCodes.CURL_NOT_FOUND_ERROR,
            log_msg="curl binary not found",
            log_args=None
        )


class PipConfigFileNotFoundError(_BaseProcessingError):
    """The pip system config file path does not exist."""

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__(
            exitcode=_ExitCodes.PIP_CONFIG_FILE_NOT_FOUND,
            log_msg="Pip configuration file not found",
            log_args=None
        )


class MissingPipConfigFileSectionError(_BaseProcessingError):
    """There is a missing section in the pip config file."""

    def __init__(self, section: str) -> None:
        """Initialize the instance.

        :param section: The name of the missing section
        """
        self.section = section
        super().__init__(
            exitcode=_ExitCodes.MISSING_PIP_CONFIG_SECTION,
            log_msg="Pip configuration file: no section %s",
            log_args=[self.section]
        )


class MissingPipConfigFileOptionError(_BaseProcessingError):
    """There is a missing option in a given section of the pip config file."""

    def __init__(self, section: str, option: str) -> None:
        """Initialize the instance.

        :param section: The name of the section where the option is missing
        :param option: The name of the missing option
        """
        self.section = section
        self.option = option
        super().__init__(
            exitcode=_ExitCodes.MISSING_PIP_CONFIG_OPTION,
            log_msg="Pip configuration file: section %s: no option %s",
            log_args=[self.section, self.option]
        )


class RunHasNoError(_BaseProcessingError):
    """The run was successful.

    This is not an error stricty speaking, but we use it because it inherits
    of the logging and exit facilities provided by the super class.
    """

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__(
            exitcode=_ExitCodes.SUCCESS,
            log_msg=None,
            log_args=None,
        )


class ConfiguredJFrogUrlParsingError(_BaseProcessingError):
    """There was an error while parsing the JFrog URL."""

    def __init__(self, url: str, cause: Exception | str) -> None:
        """Initilize the instance.

        :param url: The url which makes an error
        :param cause: The cause of the error, either an exception or an
            explaining string
        """
        self.url = url
        if isinstance(cause, Exception):
            cause = str(cause)
        super().__init__(
            exitcode=_ExitCodes.FAILED_PARSING_CONFIGURED_JFROG_URL,
            log_msg="URL %s has unexpected layout, cannot parse: %s",
            log_args=[self.url, cause]
        )


TAnyProcessingError = (
    ProblemWhileRunningCurlError,
    UnsupportedOperatingSystemError,
    AppDataNotSetError,
    SystemRootNotSetError,
    CurlNotFoundError,
    PipConfigFileNotFoundError,
    MissingPipConfigFileSectionError,
    MissingPipConfigFileOptionError,
    RunHasNoError,
    ConfiguredJFrogUrlParsingError
)
