# url

A small, dependency-free CLI tool to inspect and pretty-print components of an absolute URL.

It is designed as a quick helper you can drop into your shell toolkit to:

* normalize URLs in a consistent way,
* see and debug individual parts (scheme, host, path, query, fragment),
* inspect parsed query parameters.

---

## Features

1. Accepts an absolute URL either as an argument or via stdin
2. Prints a single **normalized URL** line:
    * scheme/host lowercased,
    * default ports removed (80 for HTTP, 443 for HTTPS),
    * compacted path (no redundant trailing slash, except for `/`),
    * empty path replaced by `/` when appropriate
3. Shows URL components: scheme, username, password, hostname, port, path, fragment, query
4. Parses and prints query parameters as `key = value` pairs in order
5. Optional colored output (ANSI) for better readability
6. Simple, deterministic exit codes for scripting

> [!TIP]
> Think of `url` as a small URL inspector: it does not fetch anything over the network;
> it only parses and pretty-prints what you give it.

---

## Requirements

* Python 3.8+ (system Python is sufficient)
* POSIX-like environment (Linux, macOS, WSL, etc.)

No third-party Python packages are required!

---

## Installation

Assuming you have cloned or downloaded the repository that contains `url-inspect.py`.

### 1. Make the script executable

```bash
chmod +x url-inspect.py
```

You can now run it directly:

```bash
./url-inspect.py "https://example.com/path?a=1&b=2#frag"
```

### 2. (Optional) Install as `url` on your PATH

If you want a short, convenient command name (`url`), you can rename or link it into a directory on your `PATH`.

**Option A: rename and move:**

```bash
mv url-inspect.py url
chmod +x url
sudo mv url /usr/local/bin/
```

**Option B: keep the filename and create a symlink:**

```bash
chmod +x /path/to/url-inspect.py
ln -s /path/to/url-inspect.py ~/.local/bin/url
```

Make sure `~/.local/bin` is included in your `PATH`.

> [!TIP]
> The script defines the CLI name as `url` (via `argparse.ArgumentParser(prog="url")`).
> Using `url` as the command name will match examples and help output.

---

## Quick start

Assuming the command is available as `url`.

### URL as an argument

```bash
url "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4317824011"
```

Example output (colors omitted here):

```text
Normalized: https://www.linkedin.com/jobs/collections/recommended?currentJobId=4317824011

Components:
  scheme: https
  hostname: www.linkedin.com
  path: /jobs/collections/recommended/
  query: currentJobId=4317824011
  parameters:
    - currentJobId = 4317824011
```

### URL from stdin

```bash
printf 'https://example.com/path?a=1&b=2#frag' | url
```

Or using `-` explicitly:

```bash
printf 'https://example.com/path?a=1&b=2#frag' | url -
```

This is useful when:

* you copy a URL into the clipboard and paste it into the terminal,
* you generate URLs from another tool or script,
* you want to avoid shell interpretation of `?`, `&`, `#`, etc.

> [!TIP]
> Passing the URL via stdin is often the safest option when it contains characters that the shell might interpret.

### Disable colors

If you prefer plain output (for logs or scripts), use:

```bash
url --no-color "https://example.com/path?a=1&b=2"
```

When stdout is not a TTY (e.g. when you redirect output to a file), the script also disables colors automatically.

---

## Command-line usage

Basic syntax:

```bash
url [URL | -] [--no-color]
```

* If `URL` is provided and not equal to `-`, it is parsed directly.
* If `URL` is omitted or set to `-`, the tool reads a single URL from stdin.

### Options

| Option       | Type       | Default | Description                                       |
|--------------|------------|---------|---------------------------------------------------|
| `url`        | positional | —       | Absolute URL to parse, or `-` to read from stdin. |
| `--no-color` | flag       | `False` | Disable ANSI colors in output.                    |

> [!IMPORTANT]
> If you call `url -` or omit the URL argument, **stdin must contain a non-empty string**. 
> If stdin is a TTY and no data is piped, the tool returns a usage error.

---

## URL validation & normalization

The tool intentionally accepts only **absolute URLs**.

### What is considered a valid URL?

A URL is accepted if all the following hold:

1. It contains **no whitespace** characters
2. `scheme` is non-empty (e.g. `https`)
3. `netloc` is non-empty (e.g. `example.com` or `user:pass@host:443`)
4. Parsed `hostname` is non-empty

Examples of **accepted** URLs:

* `https://example.com`
* `https://example.com/path?a=1&b=2#frag`
* `https://user:pass@example.com:443/foo/bar`

Examples of **rejected** inputs:

* `example.com` (no scheme)
* `/foo/bar` (relative path, no host)
* `https://` (no host)
* `https://exa mple.com/path` (contains whitespace)

When input is rejected, `url` prints a clear error to stderr and exits with a non-zero code.

### Normalization rules

Normalization is heuristic but consistent:

1. Scheme is lowercased (e.g. `HTTPS` → `https`).
2. Hostname is lowercased (e.g. `Example.COM` → `example.com`).
3. Default ports are stripped:
    * `http://example.com:80` → `http://example.com`
    * `https://example.com:443` → `https://example.com`
4. Empty path becomes `/`.
5. For **origin-only** URLs (no path, query, or fragment), only `scheme://netloc` is printed:
    * `https://example.com` → `https://example.com`
6. For non-root paths, a trailing slash is removed in the normalized form (query and fragment are preserved):
    * `https://example.com/foo/` → `https://example.com/foo`

The raw components (path, query, fragment) are taken from Python's `urllib.parse.urlparse()` without additional decoding.

> [!NOTE]
> The goal of normalization is to obtain a compact, human-friendly URL.
> It is **not** a full canonicalization algorithm suitable for security or caching decisions.

---

## Output structure

Given a valid URL, `url` prints:

1. A single `Normalized:` line
2. A `Components:` block
3. Optionally, a `parameters:` section if a query string is present

Example:

```text
Normalized: https://example.com/path?a=1&b=2

Components:
  scheme: https
  hostname: example.com
  path: /path
  query: a=1&b=2
  parameters:
    - a = 1
    - b = 2
```

Component rules:

* `scheme` is always printed.
* `username`, `password`, `hostname`, `port`, `path`, `fragment` are printed only if non-empty.
* If there is a query string, `query` is printed as-is and `parameters:` shows parsed key/value pairs in order. Blank values are preserved.

---

## Exit codes

* `0` - success
* `1` - usage error (for example, no URL provided and stdin is empty)
* `2` - input is not considered a valid absolute URL

In error cases, a descriptive message is printed to stderr.

---

## Examples for scripting

### Inspect URLs from a file

```bash
while read -r line; do
  echo "--- $line" >&2
  printf '%s' "$line" | url --no-color
done < urls.txt
```

### Quickly see query parameters

```bash
url "https://example.com/search?q=uuid&lang=en&debug=1"
```

### Integrate with other tools

```bash
# Example: inspect a URL produced by some script
./generate-link.sh | url

# Example: fetch a Location header and inspect it
curl -I https://example.com \
  | awk -F': ' '/^Location:/ {print $2}' \
  | tr -d '\r' \
  | url
```

---

## License & disclaimer

This project is licensed under the [MIT License](./LICENSE).

> [!IMPORTANT]
> This tool parses and prints URLs — it does not validate ownership,security, or reachability of the targets.
> Do not rely solely on its output for security decisions.

---

## Contributing

Issues and pull requests are welcome.
If you would like to propose new behaviors or formatting options, please include concrete examples and a brief rationale
so we can keep `url-inspect` small, understandable, and focused on its core job :mag_right:
