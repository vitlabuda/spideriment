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


from typing import Optional, List, Dict
import threading
import urllib.parse as urlparse
import urllib.robotparser as robotparser
from Settings import Settings
from URLWrapper import URLWrapper
from RequestsWrapper import RequestsWrapper, RequestsWrapperException


class RobotsWrapper:
    _robots_cache: Dict[str, Optional[robotparser.RobotFileParser]] = {}
    _robots_cache_lock: threading.Lock = threading.Lock()

    def __init__(self, url_wrapper: URLWrapper):
        self._url_wrapper: URLWrapper = url_wrapper
        self._cache_key: str = url_wrapper.parsed_url.netloc
        self._robots_url: str = self._generate_robots_url(url_wrapper.parsed_url)

    @staticmethod
    def can_be_crawled_according_to_robots_meta_tag(tag_contents: str) -> bool:
        # not really according to standard, but it's really simple (and won't cause any disallowed crawling/parsing)
        tag_contents = tag_contents.lower()
        return ("noindex" not in tag_contents) and ("nofollow" not in tag_contents)

    def _generate_robots_url(self, parsed_url: urlparse.ParseResult) -> str:
        return parsed_url.scheme + "://" + parsed_url.netloc + "/robots.txt"

    def can_be_crawled(self, cache_only: bool = False) -> bool:
        if self._is_url_in_always_allow_list():
            return True

        robot_file_parser = self._get_robots_file_parser(cache_only)
        if robot_file_parser is None:
            return True  # if the robots file fails to fetch (or is not in cache, if cache_only is True), assume crawling is allowed

        # robotparser shouldn't raise any exceptions
        return robot_file_parser.can_fetch(Settings.ROBOTS_TXT_USER_AGENT, self._url_wrapper.url)

    def _is_url_in_always_allow_list(self) -> bool:
        for always_allow_url_wrapper in Settings.ROBOTS_TXT_ALWAYS_ALLOW_URLS:
            if self._url_wrapper.canonical_url == always_allow_url_wrapper.canonical_url:
                return True
        return False

    def _get_robots_file_parser(self, cache_only: bool) -> Optional[robotparser.RobotFileParser]:
        RobotsWrapper._robots_cache_lock.acquire()
        try:
            if self._cache_key in RobotsWrapper._robots_cache:
                return RobotsWrapper._robots_cache[self._cache_key]
        finally:
            RobotsWrapper._robots_cache_lock.release()

        if cache_only:
            return None  # if cache_only is True and the item isn't in cache, return None

        return self._fetch_robots_file()

    def _fetch_robots_file(self) -> Optional[robotparser.RobotFileParser]:
        try:
            requests_wrapper = RequestsWrapper(self._robots_url, "text/plain", Settings.MAX_ROBOTS_FETCH_SIZE)
            robots_text = requests_wrapper.fetch_text_only_and_skip_url_check()
        except RequestsWrapperException:
            self._add_parser_to_robots_cache(None)  # if item is not present in cache, save it, if there is space
            return None

        robots_lines = self._minify_robots_file_and_split_it_to_lines(robots_text)
        robots_file_parser = robotparser.RobotFileParser()
        robots_file_parser.parse(robots_lines)

        self._add_parser_to_robots_cache(robots_file_parser)  # if item is not present in cache, save it there, if there is space
        return robots_file_parser

    def _add_parser_to_robots_cache(self, parser: Optional[robotparser.RobotFileParser]) -> None:
        RobotsWrapper._robots_cache_lock.acquire()
        try:
            if len(RobotsWrapper._robots_cache) < Settings.MAX_ROBOTS_CACHE_ENTRIES:
                RobotsWrapper._robots_cache[self._cache_key] = parser
        finally:
            RobotsWrapper._robots_cache_lock.release()

    def _minify_robots_file_and_split_it_to_lines(self, robots_text: str) -> List[str]:
        # remove useless data (comments and empty lines) from the robots file, so it isn't unnecessarily cached
        minified_lines = []

        for line in robots_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            minified_lines.append(line)

        return minified_lines
