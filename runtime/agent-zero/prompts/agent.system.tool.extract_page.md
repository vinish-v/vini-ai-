### extract_page
fast read-only webpage extraction without opening the live browser
arg: `url` http(s) URL to fetch
arg: `max_chars` optional extracted text limit
arg: `timeout` optional request timeout in seconds
returns title, description, readable content, links, headings, forms, selector hints, content fingerprint, and explicit blocked/error state

Use this before visible browser automation when the task only needs page text,
links, headings, or form structure. If the page is blocked, JavaScript-heavy,
requires login, or needs visual proof, switch to the `browser` tool instead of
pretending extraction succeeded.

example:
~~~json
{
  "tool_name": "extract_page",
  "tool_args": {
    "url": "https://example.com",
    "max_chars": 12000
  }
}
~~~
