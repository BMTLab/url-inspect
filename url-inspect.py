#!/usr/bin/python3

"""
Name: url-inspect.py
Author: Nikita Neverov (BMTLab)
Version: 1.0.0
Date: 2025-11-21
License: MIT

Description
-----------
Small CLI tool to inspect and pretty-print components of an absolute URL.

It prints:

- A single normalized URL line
  (lowercased scheme/host, default ports removed,
  compacted path without redundant trailing slashes, etc.).
- Individual parts (scheme, user, password, host, port, path, query, fragment).
- Parsed query parameters (key/value pairs).

Notes
-----
- The tool intentionally accepts only *absolute* URLs
  with a non-empty scheme and network location
  (for example ``"https://example.com/..."``).
- Relative references like ``"/foo/bar"`` or bare hosts like
  ``"example.com"`` are treated as "not a URL" for safety and simplicity.

Usage
-----
URL as an argument (quoted or without special characters)::
    url "https://user:pass@example.com:443/foo/bar?x=1&y=2#frag"

URL from stdin (safe, shell does not interpret it)::
    past | url
    echo 'https://example.com/path?a=1&b=2#frag' | url

Options
-------
- ``url URL``          - parse URL from argument.
- ``url -``            - read URL from stdin.
- ``url --no-color``   - disable ANSI colors in output.

Exit codes
----------
  0  Success.
  1  Usage error (no input URL).
  2  Input is not considered a valid absolute URL.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any
from urllib.parse import ParseResult, parse_qsl, urlparse, urlunparse


class AnsiColors:
    """Container for ANSI color escape sequences.

    The actual values depend on whether colors are enabled.
    If colors are disabled, all attributes are set to an empty string
    so that formatted output remains readable without color support.

    Parameters
    ----------
    enabled : bool
        Flag indicating whether color output should be enabled.
    """

    __slots__ = ("reset", "bold", "dim", "cyan", "green", "yellow", "magenta")

    def __init__(self, enabled: bool) -> None:
        if enabled:
            self.reset: str = "\033[0m"
            self.bold: str = "\033[1m"
            self.dim: str = "\033[2m"
            self.cyan: str = "\033[36m"
            self.green: str = "\033[32m"
            self.yellow: str = "\033[33m"
            self.magenta: str = "\033[35m"
        else:
            self.reset = ""
            self.bold = ""
            self.dim = ""
            self.cyan = ""
            self.green = ""
            self.yellow = ""
            self.magenta = ""


@dataclass(frozen=True, slots=True)
class UrlView:
    """View model describing a parsed and normalized URL.

    Attributes
    ----------
    raw : str
        Original URL string as provided by the user.
    parsed : urllib.parse.ParseResult
        Parsed URL components.
    normalized : str
        Normalized and compact textual representation of the URL.
    query_params : list[tuple[str, str]]
        Sequence of query parameters in (key, value) form.
    """

    raw: str
    parsed: ParseResult
    normalized: str
    query_params: list[tuple[str, str]]


_DEFAULT_PORTS: dict[str, int] = {
    "http": 80,
    "https": 443,
}

EXIT_OK: int = 0
EXIT_USAGE: int = 1
EXIT_NOT_URL: int = 2

# Maximum number of URL characters to show in error messages.
ERROR_URL_PREVIEW_LEN: int = 15


def eprint(*args: Any) -> None:
    """Print the given arguments to stderr.

    Parameters
    ----------
    *args : Any
        Objects to print. They are passed directly to :func:`print`.
    """
    # noinspection PyTypeChecker
    print(*args, file=sys.stderr)


def preview_for_error(url: str, max_len: int = ERROR_URL_PREVIEW_LEN) -> str:
    """Return a shortened preview of the URL for error messages.

    Parameters
    ----------
    url : str
        Full URL string.
    max_len : int, optional
        Maximum number of characters to include in the preview
        before appending ``"..."``. Defaults to ``ERROR_URL_PREVIEW_LEN``.

    Returns
    -------
    str
        Preview string suitable for use in error messages.
    """
    if len(url) <= max_len:
        return url

    return f"{url[:max_len]}..."


def parse_absolute_url(url: str) -> ParseResult:
    """Parse and validate an absolute URL.

    Validation rules (heuristic but strict for CLI use)
    ---------------------------------------------------
    - No whitespace characters are allowed.
    - Parsed scheme must be non-empty.
    - Parsed netloc must be non-empty.
    - Parsed hostname must be non-empty.

    Parameters
    ----------
    url : str
        Input URL string.

    Returns
    -------
    urllib.parse.ParseResult
        Parsed URL components.

    Raises
    ------
    ValueError
        If the input does not satisfy the conditions for an absolute URL.
    """
    if not url:
        raise ValueError("URL is empty")

    # Single-pass check; short-circuits as soon as whitespace is found
    for ch in url:
        if ch.isspace():
            raise ValueError("URL must not contain whitespace")

    parsed: ParseResult = urlparse(url)

    if not parsed.scheme:
        raise ValueError("URL must have a non-empty scheme")
    if not parsed.netloc:
        raise ValueError("URL must have a network location (host[:port])")
    if parsed.hostname is None or parsed.hostname == "":
        raise ValueError("URL must have a hostname")

    return parsed


def _build_netloc(
        username: str,
        password: str,
        host: str,
        port: int | None,
) -> str:
    """Build the ``netloc`` component from userinfo, host and port.

    Parameters
    ----------
    username : str
        Username part, or an empty string if not present.
    password : str
        Password part, or an empty string if not present.
    host : str
        Hostname (already normalized if needed).
    port : int or None
        Port number if present, otherwise ``None``.

    Returns
    -------
    str
        Netloc string in the form ``"user:pass@host:port"``
        with individual parts omitted if not present.
    """
    userinfo: str = ""
    if username:
        userinfo = username
        if password:
            userinfo += f":{password}"
        userinfo += "@"

    hostport: str = host
    if port is not None:
        hostport = f"{host}:{port}"

    return userinfo + hostport


def _normalized_components(parsed: ParseResult) -> tuple[str, str, str, str, str, str]:
    """Return normalized URL components suitable for ``urlunparse``.

    Normalization rules
    -------------------
    - Scheme is lowercased.
    - Hostname is lowercased.
    - Default ports (80 for http, 443 for https) are stripped.
    - Empty path is replaced with ``"/"``.
    - Query and fragment are preserved as-is.

    Parameters
    ----------
    parsed : urllib.parse.ParseResult
        Parsed URL components.

    Returns
    -------
    tuple of str
        Tuple ``(scheme, netloc, path, params, query, fragment)`` ready
        to be passed to :func:`urllib.parse.urlunparse`.
    """
    scheme: str = parsed.scheme.lower()

    username: str = parsed.username or ""
    password: str = parsed.password or ""
    host: str = (parsed.hostname or "").lower()
    port: int | None = parsed.port

    default_port: int | None = _DEFAULT_PORTS.get(scheme)
    if default_port is not None and port == default_port:
        port = None

    netloc: str = _build_netloc(username=username, password=password, host=host, port=port)

    path: str = parsed.path or "/"
    params: str = ""
    query: str = parsed.query
    fragment: str = parsed.fragment

    return scheme, netloc, path, params, query, fragment


def normalized_compact_url(parsed: ParseResult) -> str:
    """Return a normalized and compact representation of a URL.

    Combined behavior
    -----------------
    - First normalizes components
      (scheme/host lowercased, default ports stripped, path defaulting to ``"/"``).
    - If path is empty or ``"/"``, and query and fragment are empty,
      returns only the origin: ``"scheme://netloc"``.
    - Otherwise, uses the normalized URL but removes a trailing ``"/"`` from the path,
      except for the root ``"/"``.

    Parameters
    ----------
    parsed : urllib.parse.ParseResult
        Parsed URL components.

    Returns
    -------
    str
        Normalized and compact URL string.
    """
    scheme, netloc, path, params, query, fragment = _normalized_components(parsed)

    # Common fast path for origin-only URLs.
    if (path == "" or path == "/") and not query and not fragment:
        return f"{scheme}://{netloc}"

    if path.endswith("/") and path != "/":
        path = path[:-1]

    return urlunparse((scheme, netloc, path, params, query, fragment))


def format_query_params(parsed: ParseResult) -> list[tuple[str, str]]:
    """Extract query parameters as ``(key, value)`` pairs.

    Parameters
    ----------
    parsed : urllib.parse.ParseResult
        Parsed URL components.

    Returns
    -------
    list[tuple[str, str]]
        List of query parameters in the order they appear in the query string.
        Blank values are preserved.
    """
    return parse_qsl(parsed.query, keep_blank_values=True)


def build_url_view(raw_url: str, parsed: ParseResult) -> UrlView:
    """Create a :class:`UrlView` from the raw URL and parsed components.

    Parameters
    ----------
    raw_url : str
        Original URL string as provided by the user.
    parsed : urllib.parse.ParseResult
        Parsed URL components.

    Returns
    -------
    UrlView
        View model with normalized URL and parsed query parameters.
    """
    normalized: str = normalized_compact_url(parsed)
    query_params: list[tuple[str, str]] = format_query_params(parsed)
    return UrlView(
        raw=raw_url,
        parsed=parsed,
        normalized=normalized,
        query_params=query_params,
    )


def print_kv(
        key: str,
        value: str | None,
        colors: AnsiColors,
        indent: int = 0,
) -> None:
    """Print a colored key–value pair.

    Parameters
    ----------
    key : str
        Label to print (for example ``"scheme"``).
    value : str or None
        Value to print. If ``None``, a dash ``"-"`` is rendered.
    colors : AnsiColors
        Active color palette.
    indent : int, optional
        Number of leading spaces to insert before the key.
    """
    prefix: str = " " * indent
    rendered: str = value if value is not None else "-"
    print(f"{prefix}{colors.cyan}{key}:{colors.reset} {rendered}")


def print_opt_str(
        key: str,
        value: str | None,
        colors: AnsiColors,
        indent: int = 0,
) -> None:
    """Print a string component only if its value is truthy.

    Parameters
    ----------
    key : str
        Label to print.
    value : str or None
        Value to print if non-empty.
    colors : AnsiColors
        Color palette.
    indent : int, optional
        Number of leading spaces to insert before the key.
    """
    if value:
        print_kv(key, value, colors, indent=indent)


def print_opt_int(
        key: str,
        value: int | None,
        colors: AnsiColors,
        indent: int = 0,
) -> None:
    """Print an integer component only if its value is not ``None``.

    Parameters
    ----------
    key : str
        Label to print.
    value : int or None
        Integer value to print if present.
    colors : AnsiColors
        Color palette.
    indent : int, optional
        Number of leading spaces to insert before the key.
    """
    if value is not None:
        print_kv(key, str(value), colors, indent=indent)


def print_url_info(view: UrlView, colors: AnsiColors) -> None:
    """Pretty-print information about the given URL view.

    Parameters
    ----------
    view : UrlView
        URL view model to render.
    colors : AnsiColors
        Color palette used for highlighting keys and sections.
    """
    parsed: ParseResult = view.parsed

    # Single combined normalized + compacted representation
    print_kv("Normalized", view.normalized, colors)
    print()

    print(f"{colors.bold}Components:{colors.reset}")
    # Scheme is guaranteed non-empty after validation
    print_kv("scheme", parsed.scheme, colors, indent=2)

    username: str | None = parsed.username
    password: str | None = parsed.password
    hostname: str | None = parsed.hostname
    port: int | None = parsed.port
    path: str = parsed.path
    fragment: str = parsed.fragment
    query: str = parsed.query

    print_opt_str("username", username, colors, indent=2)
    print_opt_str("password", password, colors, indent=2)
    print_opt_str("hostname", hostname, colors, indent=2)
    print_opt_int("port", port, colors, indent=2)
    print_opt_str("path", path, colors, indent=2)
    print_opt_str("fragment", fragment, colors, indent=2)

    if query:
        print_kv("query", query, colors, indent=2)
        params: list[tuple[str, str]] = view.query_params
        if params:
            print(f"{' ' * 2}{colors.magenta}parameters:{colors.reset}")
            for key, value in params:
                print(f"    - {colors.cyan}{key}{colors.reset} = {value}")
    print()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments for the URL CLI.

    Parameters
    ----------
    argv : Sequence[str]
        Argument vector, usually ``sys.argv[1:]``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments namespace.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="url",
        description=(
            "Print out the parts of an absolute URL in a structured way. "
            "If URL is omitted or set to '-', it will be read from stdin."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="The URL to parse. Use '-' or omit to read from stdin.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in output.",
    )

    # argparse accepts any sequence of strings; no need to wrap into list()
    return parser.parse_args(argv)


def read_url_from_stdin() -> str:
    """Read a URL string from stdin and strip surrounding whitespace.

    Returns
    -------
    str
        URL read from stdin, with leading and trailing whitespace removed.

    Raises
    ------
    SystemExit
        If stdin is a TTY (no piped data) or the resulting string is empty.
    """
    if sys.stdin.isatty():
        eprint("ERROR: URL must be provided as argument or via stdin.")
        raise SystemExit(EXIT_USAGE)

    data: str = sys.stdin.read()
    url: str = data.strip()
    if not url:
        eprint("ERROR: stdin is empty; no URL to parse.")
        raise SystemExit(EXIT_USAGE)

    return url


def resolve_url_argument(args: argparse.Namespace) -> str:
    """Determine the URL to use, either from arguments or stdin.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    str
        URL string to inspect.

    Raises
    ------
    SystemExit
        If neither a URL argument nor valid stdin data is available.
    """
    arg_url: str | None = args.url
    if arg_url is not None and arg_url != "-":
        return arg_url

    return read_url_from_stdin()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the URL inspection CLI.

    Parameters
    ----------
    argv : Sequence[str] or None, optional
        Command-line arguments excluding the program name.
        If ``None``, ``sys.argv[1:]`` is used.

    Returns
    -------
    int
        Exit status code. ``0`` on success, non-zero on error.
    """
    if argv is None:
        argv = sys.argv[1:]

    args: argparse.Namespace = parse_args(argv)
    url_text: str = resolve_url_argument(args)

    try:
        parsed: ParseResult = parse_absolute_url(url_text)
    except ValueError as exc:
        preview: str = preview_for_error(url_text)
        eprint(
            f"ERROR: input is not recognized as a valid absolute URL: "
            f"{preview!r} ({exc})",
        )
        return EXIT_NOT_URL

    enable_colors: bool = sys.stdout.isatty() and not args.no_color
    colors: AnsiColors = AnsiColors(enabled=enable_colors)

    view: UrlView = build_url_view(raw_url=url_text, parsed=parsed)
    print_url_info(view, colors)

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
### End
