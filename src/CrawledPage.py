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


from typing import List, Dict
import re
import json
from Settings import Settings
from URLWrapper import URLWrapper


class CrawledPageException(Exception):
    pass


class CrawledPage:
    _WHITESPACE_MATCHING_REGEX: re.Pattern = re.compile(r'\s+')  # precompiled regex to speed-up the processing
    _LANGUAGE_IDENTIFIER_MAX_LENGTH: int = 10  # usually is something like "en-US", so even 10 is a lot

    def __init__(self, original_url: URLWrapper, final_url: URLWrapper, crawl_timestamp: int,
                 language: str, title: str, headings: Dict[str, List[str]], description: str, keywords: str, author: str,
                 content_snippet: str, content_snippet_quality: float, image_alts: str, link_texts: str, total_links_count: int):
        self.original_url: URLWrapper = original_url
        self.final_url: URLWrapper = final_url
        self.was_redirected: bool = (original_url.url != final_url.url)
        self.crawl_timestamp: int = crawl_timestamp

        self.language: str = self._clean_whitespace(language)  # length will be checked in self._verify_crawled_page()
        self.title: str = self._unify_whitespace(title.strip())[0:Settings.PAGE_TITLE_MAX_LENGTH].strip()
        self.headings: Dict[str, List[str]] = self._unify_whitespace_and_shorten_html_headings(headings)
        self.description: str = self._unify_whitespace(description.strip())[0:Settings.PAGE_DESCRIPTION_MAX_LENGTH].strip()
        self.keywords: str = self._unify_whitespace(keywords)[0:Settings.PAGE_KEYWORDS_MAX_LENGTH]
        self.author: str = self._unify_whitespace(author.strip())[0:Settings.PAGE_AUTHOR_MAX_LENGTH].strip()
        self.content_snippet: str = self._unify_whitespace(content_snippet.strip())[0:Settings.PAGE_CONTENT_SNIPPET_MAX_LENGTH].strip()
        self.content_snippet_quality: float = max(0.0, min(1.0, content_snippet_quality))  # using a float between 0.0 and 1.0 specifies, how likely the content snippet contains a useful text (e.g. text from paragraph is the most meaningful etc.)
        self.image_alts: str = self._unify_whitespace(image_alts.strip())[0:Settings.PAGE_IMAGE_ALTS_MAX_LENGTH].strip()
        self.link_texts: str = self._unify_whitespace(link_texts.strip())[0:Settings.PAGE_LINK_TEXTS_MAX_LENGTH].strip()

        self.total_links_count: int = total_links_count

        self._verify_crawled_page()

    def to_savable_dict(self) -> dict:
        return {
            "original_url": self.original_url.url,
            "final_url": self.final_url.url,
            "original_canonical_url": self.original_url.canonical_url,
            "final_canonical_url": self.final_url.canonical_url,
            "crawl_timestamp": self.crawl_timestamp,

            "language": self.language,
            "title": self.title,
            "headings": self.headings,
            "description": self.description,
            "keywords": self.keywords,
            "author": self.author,
            "content_snippet": self.content_snippet,
            "content_snippet_quality": self.content_snippet_quality,
            "image_alts": self.image_alts,
            "link_texts": self.link_texts,

            "total_links_count": self.total_links_count,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_savable_dict())

    def _verify_crawled_page(self) -> None:
        if not self.title:
            raise CrawledPageException("The title on this webpage is empty or wasn't found!")

        if not self.content_snippet:
            raise CrawledPageException("There wasn't any meaningful content on this webpage!")

        if len(self.language) > CrawledPage._LANGUAGE_IDENTIFIER_MAX_LENGTH:
            raise CrawledPageException("This HTML document's language identifier is too long! ({})".format(self.language))

    def _clean_whitespace(self, string: str) -> str:
        return CrawledPage._WHITESPACE_MATCHING_REGEX.sub("", string)

    def _unify_whitespace(self, string: str) -> str:
        return CrawledPage._WHITESPACE_MATCHING_REGEX.sub(" ", string)

    def _unify_whitespace_and_shorten_html_headings(self, html_headings: Dict[str, List[str]]) -> Dict[str, List[str]]:
        new_headings = {}

        for collection_index, (key, collection) in enumerate(html_headings.items()):
            if collection_index >= Settings.PAGE_HTML_HEADING_MAX_LEVEL:
                break

            new_collection = []

            for heading_index, heading in enumerate(collection):
                if heading_index >= Settings.PAGE_MAX_HTML_HEADINGS_PER_LEVEL:
                    break

                heading = self._unify_whitespace(heading.strip())[0:Settings.PAGE_HTML_HEADING_MAX_LENGTH].strip()
                new_collection.append(heading)

            new_headings[key] = new_collection

        return new_headings
