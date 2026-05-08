"""Various helping hand processors."""

import dataclasses
import functools
import json
import subprocess  # noqa: S404
import typing
import urllib.parse

if typing.TYPE_CHECKING:
    import logging

from .exceptions import (
    ConfiguredJFrogUrlParsingError,
    ProblemWhileRunningCurlError,
)


@dataclasses.dataclass(kw_only=True, frozen=True)
class UrlProcessor:
    """Split an URL into its component, support replacement of some parts.

    This has to be created by either:
    - either using `from_url`
    - calling `get_new_...` from an existing instance to replace values
    """

    # The fields here must match the urllib.parse.ParseResults fields
    scheme: str
    netloc: str
    path: str
    query: str
    params: str
    fragment: str
    username: str
    password: str
    hostname: str
    port: str

    @classmethod
    def from_url(cls, url: str) -> typing.Self:
        """Create an instance from an URL.

        :param url: The incoming URL.
        :return: The new instance.
        """
        parsed = urllib.parse.urlparse(url)
        vals = {
            f: getattr(parsed, f) for f in
            [f.name for f in dataclasses.fields(cls)]
        }
        return cls(**vals)

    @property
    def token(self) -> str:
        """Return the token part of the URL.

        Since there is no difference between the password and the token,
        this is an alias to `self.password`.
        """
        # We always use an OAuth token, but this is configured in the
        # password component of the URL provided in the pip.ini file.
        return self.password

    @property
    def url(self) -> str:
        """Return the url built from the fields.

        This shall return the same value as the URL passed to `self.from_url`;
        this is there because instances might be created without a completed
        URL.
        """
        # We use params and query. Usually, we only set query, but since
        # params is available, let's use it...
        return urllib.parse.ParseResult(
            scheme=self.scheme, netloc=self.netloc, path=self.path,
            params=self.params, query=self.query, fragment=self.fragment
        ).geturl()

    @property
    def url_no_credentials(self) -> str:
        """Return the URL without username, password, token."""
        return self._get_new_with_changed_fields(
            username="", password=""
        ).url

    @functools.cached_property
    def _api_path(self) -> str:
        """Return the URL with everything after ``/api`` removed."""
        pattern = "/api"
        posn = self.path.find(pattern)
        if posn < 0:
            raise ConfiguredJFrogUrlParsingError(
                self.url, f"{pattern} not found"
            )
        return self.path[:(posn + len(pattern))]

    @staticmethod
    def _concat_ensure_separator(left: str, right: str, sep: str) -> str:
        """Concatenate to values with a non duplicted separator.

        Separator present at the end of the left part or at the beginning of
        the right part are removed before doing the concatenation, so that
        the separator doesn't appear mutiple times.

        :param left: The left part to be concatated
        :param right: The right part to be concatenated
        :param sep: The separator (can be multiple characters)
        :return: The concatenated value
        """
        if not left.endswith(sep):
            left += sep
        right = right.removeprefix(sep)
        return f"{left}{right}"

    def _get_new_with_changed_fields(self, **kwargs: str) -> typing.Self:
        """Provide a new instance with the some fields changed.

        :param **kwargs: Values of fields to be changed
        :return: The new instance.
        """
        vals = dataclasses.asdict(self).copy()
        vals.update(kwargs)
        return type(self)(**vals)

    def get_new_updated_apicall(self, api_call: str) -> typing.Self:
        """Provide a new instance with changed API call.

        All other fields are the same as ``self``.

        :param api_call: The new API call, e.g. what's after the /api in the
            url. It can contain HTTP query parameters
            (``?foo=bar&spam=eggs&...``)
        :return: _description_
        """
        parsed_api_call = self.from_url(api_call)
        path = self._concat_ensure_separator(
            self._api_path, parsed_api_call.path, "/"
        )
        return self._get_new_with_changed_fields(
            path=path,
            fragment=parsed_api_call.fragment,
            query=parsed_api_call.query,
            params=parsed_api_call.params,
        )

    def get_new_add_slash_to_path(self) -> typing.Self:
        """Provide a new instance with ``/`` added after the path part.

        The ``/`` is added only if not present after the path.

        This is needed as JFrog paths are normally ending with ``/``.
        """
        if self.path_ends_with_slash:
            return self
        path = self.path + "/"
        return self._get_new_with_changed_fields(path=path)

    @property
    def path_ends_with_slash(self) -> bool:
        """Return True if the path part ends with ``/``.

        This is needed as JFrog paths are normally ending with ``/``.
        """
        return self.path[-1] == "/"


@dataclasses.dataclass(kw_only=True, frozen=True)
class CurlCommandProcessor:
    """Helper for running curl and getting output."""

    logger: logging.Logger
    cmdline: list[str]
    stdin: str | None

    @classmethod
    def _remove_empty_lines(cls, buff: str, prefix: str = "") -> str:
        """Remove the empty lines from a text.

        :param buff: The text to be processed
        :param prefix: The text to add at the beginning of the lines
        """
        def gen() -> typing.Iterator[str]:
            for ln_ in buff.split("\n"):
                ln = ln_.strip()
                if ln:
                    yield prefix + ln
        return "\n".join(gen())

    @functools.cached_property
    def _status_and_output(self) -> tuple[int, str, str]:
        """Provides returncode, raw stdout and raw stderr from execution.

        :return: returncode, stdout and stderr as tuple
        """
        self.logger.debug("Executing: %s", self.cmdline)
        cp = subprocess.Popen(  # noqa: S603
            self.cmdline,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        out, err = cp.communicate(input=self.stdin)

        if err:
            self.logger.debug(
                "Curl execution standard error content:\n%s",
                self._remove_empty_lines(err, prefix="    "),
            )
        if cp.returncode:
            cpe = subprocess.CalledProcessError(
                cp.returncode, self.cmdline,
                output=out, stderr=err
            )
            raise ProblemWhileRunningCurlError(cpe)

        return cp.returncode, out, err

    @property
    def raw_stdout(self) -> str:
        """The unprocessed command standard output."""
        return self._status_and_output[1]

    @property
    def raw_stderr(self) -> str:
        """The unprocessed command standard error."""
        return self._status_and_output[2]

    @property
    def returncode(self) -> int:
        """The command return code."""
        return self._status_and_output[0]

    @property
    def is_json_content_type(self) -> bool | None:
        """Check if the content type is JSON, based on curl output.

        :param stderr_txt: The curl standard error content
        :return: `True` or `False`, or `None` if cannot be determined.
        """
        ctp: list[str] | str
        ctp = [
            ln.strip() for ln in self.raw_stderr.split("\n")
            if "content-type" in ln.lower()
        ]
        if len(ctp) != 1:
            return None
        ctp = ctp[0].lower().rsplit("content-type:", 1)[-1].strip()
        self.logger.debug("Detected (lower case) content type: %s", ctp)
        return ctp == "application/json"

    @property
    def processed_output(self) -> object:
        """Provides the processed output from curl standard output.

        It tryies to get the content type and, if JSON, returned the parsed
        output as python object. If not JSON, returns at text.

        If the JSON processing fails, returns as text.

        If the standard output is empty, return None.

        Any non-JSON output will result in a warning log message.
        """
        if not self.raw_stdout:
            self.logger.warning("No data returned")
            return None

        is_json = self.is_json_content_type
        if is_json is None:
            self.logger.warning(
                "Cannot determine content type. Trying as JSON and falling "
                "back to text/html if failed."
            )
            try:
                return json.loads(self.raw_stdout)
            except json.decoder.JSONDecodeError:
                self.logger.warning(
                    "It seems that this is not JSON, leaving it as text"
                )
                return self.raw_stdout
        elif is_json:
            return json.loads(self.raw_stdout)
        else:
            self.logger.warning("Data is not JSON, leaving it as text")
            return self.raw_stdout
