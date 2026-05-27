import asyncio
from urllib.parse import urlparse

from helpers import dotenv, perplexity_search, duckduckgo_search
from helpers.tool import Tool, Response
from helpers.print_style import PrintStyle
from helpers.errors import handle_error
from helpers.searxng import search as searxng
from plugins._browser.helpers.extraction import extract_page

SEARCH_ENGINE_RESULTS = 10
BROWSER_PREVIEW_RESULTS = 3
FAST_EXTRACT_RESULTS = 2
FAST_EXTRACT_TIMEOUT = 6


class SearchEngine(Tool):
    async def execute(self, query="", **kwargs):


        search_payload = await self.searxng_search(query)
        preview_urls = self.extract_preview_urls(search_payload)
        extracted = await self.extract_top_results(preview_urls[:FAST_EXTRACT_RESULTS])
        searxng_result = self.format_result_searxng(search_payload, "Search Engine", extracted)
        if preview_urls:
            await self.open_urls_in_browser(preview_urls[:1])
            self.start_browser_preview(preview_urls[1:])

        await self.agent.handle_intervention(
            searxng_result
        )  # wait for intervention and handle it, if paused

        return Response(message=searxng_result, break_loop=False)


    async def searxng_search(self, question):
        return await searxng(question)

    def format_result_searxng(self, result, source, extracted=None):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"

        outputs = []
        extracted_by_url = {
            item.get("url"): item
            for item in (extracted or [])
            if isinstance(item, dict) and item.get("url")
        }
        for item in (result or {}).get("results", []):
            url = item["url"]
            extra = extracted_by_url.get(url)
            if extra and extra.get("ok"):
                content = str(extra.get("content") or "")[:1400].strip()
                fingerprint = str(extra.get("fingerprint") or "")[:12]
                outputs.append(
                    f"{item['title']}\n{url}\n{item['content']}\n\n"
                    f"Fast extraction ({extra.get('extraction_mode')}, fingerprint {fingerprint}):\n{content}"
                )
            elif extra:
                outputs.append(
                    f"{item['title']}\n{url}\n{item['content']}\n\n"
                    f"Fast extraction unavailable: {extra.get('status') or extra.get('error') or 'unknown'}"
                )
            else:
                outputs.append(f"{item['title']}\n{url}\n{item['content']}")

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip()

    def extract_preview_urls(self, result):
        if isinstance(result, Exception):
            return []

        urls = []
        seen = set()
        for item in (result or {}).get("results", []):
            url = str(item.get("url") or "").strip()
            if not self.is_previewable_url(url) or url in seen:
                continue
            urls.append(url)
            seen.add(url)
            if len(urls) >= BROWSER_PREVIEW_RESULTS:
                break
        return urls

    @staticmethod
    def is_previewable_url(url):
        parsed = urlparse(str(url or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def start_browser_preview(self, urls):
        if not urls:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.open_urls_in_browser(urls))

    async def extract_top_results(self, urls):
        if not urls:
            return []

        async def run_extract(url):
            try:
                return await asyncio.to_thread(
                    extract_page,
                    url,
                    timeout=FAST_EXTRACT_TIMEOUT,
                    max_chars=6000,
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "status": "failed",
                    "url": url,
                    "error": str(exc),
                    "extraction_mode": "static_html",
                }

        return await asyncio.gather(*(run_extract(url) for url in urls))

    async def open_urls_in_browser(self, urls):
        try:
            from plugins._browser.helpers.runtime import get_runtime

            runtime = await get_runtime(self.agent.context.id)
            listing = await runtime.call("list")
            browsers = listing.get("browsers") or []
            active_browser_id = (
                listing.get("last_interacted_browser_id")
                or (browsers[0].get("id") if browsers else None)
            )

            first = True
            for url in urls[:BROWSER_PREVIEW_RESULTS]:
                if first and active_browser_id:
                    result = await runtime.call("navigate", active_browser_id, url)
                else:
                    result = await runtime.call("open", url)
                    active_browser_id = result.get("id") or result.get("state", {}).get("id") or active_browser_id
                first = False
        except Exception as exc:
            PrintStyle.warning(f"Could not preview search results in Browser: {exc}")
