# SPDX-License-Identifier: BSD-3-Clause
#
# Copyright (c) 2021 Vít Labuda. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#  1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#     disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#     following disclaimer in the documentation and/or other materials provided with the distribution.
#  3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
#     products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from typing import List, Tuple, Union
import time
import bs4
from Settings import Settings
from Logger import Logger
from GlobalVarsHolder import GlobalVarsHolder
from URLWrapper import URLWrapper, URLWrapperException
from RequestsWrapper import RequestsWrapper, RequestsWrapperException
from CrawledPage import CrawledPage, CrawledPageException
from RobotsWrapper import RobotsWrapper


class CrawlerThread:
    class GenericCrawlerException(Exception):
        # shouldn't be used from outside of this class
        # the error message will get logged
        pass

    _CONTENT_SNIPPET_TRIES = (
        (1.0,  "p"),
        (0.75, ["b", "strong", "em"]),
        (0.4,  ["i", "u", "big"]),
        (0.15, "table"),
        (0.1,  ["span", "div"]),
        (0.05, "body")
    )

    def __init__(self, thread_id: int, crawl_queue: List[str], holder: GlobalVarsHolder):
        self.thread_id: int = thread_id
        self._crawl_queue: List[str] = crawl_queue

        # THOSE VARIABLES MUST NOT BE CHANGED FROM HERE!!!
        self._h = holder

        self.new_crawled_urls: List[str] = []
        self.new_crawl_queue: List[str] = []
        self.crawled_pages_data: List[CrawledPage] = []

    def thread_entry(self) -> None:
        Logger.thread_log(self.thread_id, "Crawler thread has started.")
        self._crawl()
        Logger.thread_log(self.thread_id, "Crawler thread has finished.")

    def _crawl(self) -> None:
        for i, url in enumerate(self._crawl_queue, 1):
            original_url = None
            final_url = None
            try:
                original_url = URLWrapper(url)
                crawled_page, fetched_file, crawled_links = self._crawl_single_url(original_url)
                final_url = fetched_file.final_url

                self.new_crawl_queue += crawled_links
                self.crawled_pages_data.append(crawled_page)

                Logger.thread_log(self.thread_id, "Saving crawled webpage! [URL {}: {}, redirected: {}, {} links added to crawl queue]"
                                  .format(i, original_url.url, final_url.url if crawled_page.was_redirected else "<not redirected>", len(crawled_links)))

            except (CrawlerThread.GenericCrawlerException, URLWrapperException, RequestsWrapperException, CrawledPageException) as e:
                url_tag = "[URL {}: {}]".format(i, original_url.url if original_url else "<unknown>")
                Logger.thread_log(self.thread_id, "Not saving crawled webpage:", str(e), url_tag)

            if original_url:
                self.new_crawled_urls.append(original_url.canonical_url)
            if final_url:
                self.new_crawled_urls.append(final_url.canonical_url)

    def _crawl_single_url(self, original_url: URLWrapper) -> Tuple[CrawledPage, RequestsWrapper.FetchedFile, List[str]]:
        if original_url.canonical_url in self._h.crawled_urls:
            raise CrawlerThread.GenericCrawlerException("This webpage was already crawled! (by original URL)")

        self._check_robots_file(original_url)

        crawl_timestamp = int(time.time())
        fetched_file = RequestsWrapper.from_url_wrapper(original_url, "text/html", Settings.MAX_PAGE_FETCH_SIZE).fetch_with_metadata()

        # this probably cannot happen, but it may be useful as a debugging measure
        if original_url.url != fetched_file.original_url.url:
            raise CrawlerThread.GenericCrawlerException("The original fetched URL differs from the URL that was supposed to be fetched!")

        if fetched_file.final_url.canonical_url in self._h.crawled_urls:
            raise CrawlerThread.GenericCrawlerException("This webpage was already crawled! (by final URL)")

        # if the request is redirected to an another host, check the robots file of that host
        if fetched_file.original_url.parsed_url.netloc != fetched_file.final_url.parsed_url.netloc:
            self._check_robots_file(fetched_file.final_url)

        parsed_html = self._parse_html(fetched_file.text)

        self._check_robots_meta_tag(parsed_html)
        self._remove_styles_and_scripts_from_html(parsed_html)

        language = self._check_and_get_page_language(parsed_html)
        title = self._get_page_title(parsed_html)
        headings = self._get_html_headings(parsed_html)
        description = self._get_meta_tag_contents(parsed_html, "description")
        keywords = self._get_meta_tag_contents(parsed_html, "keywords")
        author = self._get_meta_tag_contents(parsed_html, "author")
        content_snippet, content_snippet_quality = self._get_content_snippet(parsed_html)
        image_alts = self._get_image_alts(parsed_html)
        total_links_count, crawled_links, link_texts = self._get_links(parsed_html, fetched_file.final_url.url)

        crawled_page = CrawledPage(fetched_file.original_url, fetched_file.final_url, crawl_timestamp,
                                   language, title, headings, description, keywords, author,
                                   content_snippet, content_snippet_quality, image_alts, link_texts, total_links_count)

        return crawled_page, fetched_file, crawled_links

    def _check_robots_file(self, url_wrapper: URLWrapper) -> None:
        robots_wrapper = RobotsWrapper(url_wrapper)
        if not robots_wrapper.can_be_crawled():
            raise CrawlerThread.GenericCrawlerException("The robots file prevents fetching this website!")

    def _parse_html(self, html_text: str) -> bs4.BeautifulSoup:
        parsed_html = bs4.BeautifulSoup(html_text, "html.parser")
        if not parsed_html:
            raise CrawlerThread.GenericCrawlerException("Failed to parse the HTML document!")

        return parsed_html

    def _remove_styles_and_scripts_from_html(self, parsed_html: bs4.BeautifulSoup) -> None:
        # so we don't need to deal with them when e.g. getting the content snippet
        for useless_tag in parsed_html.find_all(["style", "script"]):
            useless_tag.decompose()

    def _check_robots_meta_tag(self, parsed_html: bs4.BeautifulSoup) -> None:
        contents = self._get_meta_tag_contents(parsed_html, "robots")
        if not RobotsWrapper.can_be_crawled_according_to_robots_meta_tag(contents):
            raise CrawlerThread.GenericCrawlerException("The robots meta tag prevents fetching this webpage!")

    def _get_meta_tag_contents(self, parsed_html: bs4.BeautifulSoup, name: str) -> str:
        contents = parsed_html.find("meta", {"name": name})
        if not contents:
            return ""

        contents = contents.get("content")
        if not contents:
            return ""

        return contents.strip()

    def _check_and_get_page_language(self, parsed_html: bs4.BeautifulSoup) -> str:
        # get the lang attribute from the HTML element
        lang = parsed_html.find("html")
        if not lang:
            return ""

        lang = lang.get("lang")
        if not lang:
            return ""

        lang = lang.strip()
        if not lang:
            return ""

        # check the lang against the list of allowed languages, if desired
        if Settings.ALLOWED_LANGUAGES is not None:
            lowercase_lang = lang.lower()
            for checked_lang in Settings.ALLOWED_LANGUAGES:
                if checked_lang.lower() in lowercase_lang:
                    break
            else:
                raise CrawlerThread.GenericCrawlerException("The language of this page ({}) is not allowed to be crawled!".format(lang))

        return lang

    def _get_page_title(self, parsed_html: bs4.BeautifulSoup) -> str:
        title = parsed_html.find("title")
        if not title:
            return ""

        title = title.get_text()
        if not title:
            return ""

        return title.strip()

    def _get_html_headings(self, parsed_html: bs4.BeautifulSoup) -> dict:
        headings = {}

        for heading_level in range(1, Settings.PAGE_HTML_HEADING_MAX_LEVEL + 1):
            heading_level = "h{}".format(heading_level)
            headings[heading_level] = []

            for heading_index, heading in enumerate(parsed_html.find_all(heading_level)):
                if heading_index >= Settings.PAGE_MAX_HTML_HEADINGS_PER_LEVEL:
                    break

                heading = heading.get_text()
                if not heading:
                    continue

                heading = heading.strip()
                if not heading:
                    continue

                headings[heading_level].append(heading)

        return headings

    def _get_content_snippet(self, parsed_html: bs4.BeautifulSoup) -> Tuple[str, float]:
        # The code will try to find some text in the specified element(s) and if it finds something, it will
        #  return it with the respective float representing the content snippet quality level. If if doesn't find
        #  anything, it will move on to the next "line".
        for quality, element in CrawlerThread._CONTENT_SNIPPET_TRIES:
            content_snippet = self._get_content_snippet_from_html_elements(parsed_html, element)
            if content_snippet:
                return content_snippet, quality

        # if there is no text found, return an empty string along with 0.0 quality
        return "", 0.0

    def _get_content_snippet_from_html_elements(self, parsed_html: bs4.BeautifulSoup, element_name: Union[str, list]) -> str:
        # auxiliary function for self._get_content_snippet, so it isn't cluttered with repeating code
        content_snippet = ""
        for paragraph in parsed_html.find_all(element_name):
            if len(content_snippet) >= Settings.PAGE_CONTENT_SNIPPET_MAX_LENGTH:
                break

            paragraph = paragraph.get_text()
            if not paragraph:
                continue

            paragraph = paragraph.strip()
            if not paragraph:
                continue

            content_snippet += paragraph
            content_snippet += " "  # force whitespace between paragraphs

        return content_snippet.strip()

    def _get_image_alts(self, parsed_html: bs4.BeautifulSoup) -> str:
        image_alts = ""
        for image_element in parsed_html.find_all("img"):
            if len(image_alts) >= Settings.PAGE_IMAGE_ALTS_MAX_LENGTH:
                break

            alt = image_element.get("alt")
            if not alt:
                continue

            alt = alt.strip()
            if not alt:
                continue

            image_alts += alt
            image_alts += " "  # force whitespace between image alts

        return image_alts.strip()

    def _get_links(self, parsed_html: bs4.BeautifulSoup, current_page_url: str) -> Tuple[int, List[str], str]:
        total_links_count = 0
        links = []
        link_texts = ""

        for link in parsed_html.find_all("a", href=True):
            link_href = link.get("href")
            if not link_href:
                continue

            link_href = link_href.strip()
            if not link_href:
                continue

            try:
                link_href_wrapper = URLWrapper.from_possible_relative_url(current_page_url, link_href)
                link_href = link_href_wrapper.url
            except URLWrapperException:
                continue

            total_links_count += 1

            if len(links) < Settings.PAGE_MAX_CRAWLED_LINKS_PER_WEBPAGE:
                # The if statements could be squashed, but this is more readable.
                # If the pre-checking is disabled or the pre-check is successful, add the link to the crawl queue.
                if not Settings.PRECHECK_ROBOTS_ALLOWANCE_OF_CRAWLED_LINKS or RobotsWrapper(link_href_wrapper).can_be_crawled(cache_only=True):
                    links.append(link_href)

            if len(link_texts) < Settings.PAGE_LINK_TEXTS_MAX_LENGTH:
                link_text = link.get_text()
                if link_text:
                    link_text = link_text.strip()
                    if link_text:
                        link_texts += link_text
                        link_texts += " "

        return total_links_count, links, link_texts.strip()
