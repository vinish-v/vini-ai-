### search_engine
find live news, prices, and other real-time web data
arg: `query` (keyword-based text search query)
returns urls, titles, and descriptions

When search results contain real source URLs, Vini AI opens the top source pages
in the visible Vini AI Computer Browser so users can see which sites are being
used. Use the Browser tool after search when you need rendered-page inspection,
screenshots, forms, login, or step-by-step browsing.

Search also attempts a fast static extraction of the top source pages. Treat
that extraction as a read-only acceleration lane: if it reports blocked,
empty, malformed, or JavaScript-heavy content, switch to visible Browser work
or a configured Firecrawl connector. Do not invent source content when
extraction fails.

query rules:
- use keywords, names, exact phrases, model/version numbers, dates, and domains
- do not write a natural-language question or sentence
- omit filler words like "what", "who", "can you tell me", "find information about"
- use 3-10 high-signal terms; add alternatives only when they improve recall
- bad: "What is the latest LiteLLM release and what changed?"
- good: "LiteLLM latest release notes changelog"

example:
~~~json
{
  "thoughts": ["I need current information rather than relying on memory."],
  "headline": "Searching the web",
  "tool_name": "search_engine",
  "tool_args": {
    "query": "LiteLLM latest release notes changelog"
  }
}
~~~
