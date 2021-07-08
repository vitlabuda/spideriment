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


from __future__ import annotations
import re
import urllib.parse as urlparse
from Settings import Settings


class URLWrapperException(Exception):
    pass


# this class is used very often, so it's a nice thing to have it optimized
class URLWrapper:
    # precompiled regexes to allow faster URL processing
    _URL_PATH_MULTISLASH_FIX_REGEX: re.Pattern = re.compile(r'/+')
    _URL_HOSTNAME_BASIC_CHECK_REGEX: re.Pattern = re.compile(r'^[0-9a-z.-]+$')
    _URL_HOSTNAME_DOUBLEDOTS_CHECK_REGEX: re.Pattern = re.compile(r'[.-]{2,}')

    def __init__(self, absolute_url: str):
        self._check_url_length(absolute_url)

        # seems like urlparse doesn't raise any exceptions
        try:
            parsed_url = urlparse.urlparse(absolute_url)
        except ValueError:
            raise URLWrapperException("The URL is invalid!")

        parsed_url = self._canonicalize_parsed_url(parsed_url)

        url = parsed_url.geturl().strip()  # final, canonilized url
        self._check_url_length(url)  # the url might be longer due to url encoding etc.

        self._validate_url(parsed_url, url)
        self._validate_wikipedia_url(parsed_url.netloc)

        self.parsed_url: urlparse.ParseResult = parsed_url
        self.url: str = url
        self.canonical_url: str = self._generate_canonical_url(parsed_url).strip()

    @classmethod
    def from_possible_relative_url(cls, base_url: str, relative_url: str) -> URLWrapper:
        try:
            absolute_url = urlparse.urljoin(base_url, relative_url)
        except ValueError:
            raise URLWrapperException("The URL is invalid!")

        return cls(absolute_url)

    def _check_url_length(self, url: str) -> None:
        if len(url) > Settings.URL_MAX_LENGTH:
            raise URLWrapperException("The URL is too long! ({})".format(len(url)))

    def _canonicalize_parsed_url(self, parsed_url: urlparse.ParseResult) -> urlparse.ParseResult:
        scheme = parsed_url.scheme.strip().lower()
        netloc = parsed_url.netloc.strip().lower().strip(".").strip()
        path = URLWrapper._URL_PATH_MULTISLASH_FIX_REGEX.sub('/', parsed_url.path).strip()
        query = self._remove_useless_query_string_params(parsed_url.query.strip()).strip()

        parsed_url = parsed_url._replace(scheme=scheme)
        parsed_url = parsed_url._replace(netloc=netloc)
        parsed_url = parsed_url._replace(path=path)
        parsed_url = parsed_url._replace(params="")  # those params are used basically only for JSESSIONID which is not needed at all
        parsed_url = parsed_url._replace(query=query)
        parsed_url = parsed_url._replace(fragment="")

        return parsed_url

    def _remove_useless_query_string_params(self, query_string: str) -> str:
        remaining_params = []

        try:
            parsed_qs = urlparse.parse_qsl(query_string)
        except ValueError:
            raise URLWrapperException("The query string is invalid!")

        for key, value in parsed_qs:
            key = key.strip()
            key_cmp = key.lower()
            if key_cmp.startswith("utm_") or key_cmp == "fbclid":
                continue
            remaining_params.append((key, value.strip()))

        try:
            return urlparse.urlencode(remaining_params)
        except ValueError:
            raise URLWrapperException("The query string is invalid!")

    def _validate_url(self, parsed_url: urlparse.ParseResult, url: str) -> None:
        # shouldn't happen, but the web is a weird place
        if url.count("\x00") != 0 or url.count("\r") != 0 or url.count("\n") != 0:
            raise URLWrapperException("The URL contains a NULL or newline character!")

        scheme = parsed_url.scheme
        if scheme != "http" and scheme != "https":
            raise URLWrapperException("Invalid URL scheme! ({})".format(scheme))

        hostname = parsed_url.netloc  # netloc isn't always supposed to look like a hostname, but it's not used much for public services
        if not URLWrapper._URL_HOSTNAME_BASIC_CHECK_REGEX.match(hostname) or URLWrapper._URL_HOSTNAME_DOUBLEDOTS_CHECK_REGEX.search(hostname) or (hostname.count(".") < 1):
            raise URLWrapperException("Invalid URL netloc! (doesn't look like a hostname; {})".format(hostname))

        if Settings.HOSTNAME_FILTER and Settings.HOSTNAME_FILTER.search(hostname):
            raise URLWrapperException("This URL's hostname is filtered! ({})".format(hostname))

        if not Settings.CRAWL_MOBILE_PAGES and (hostname.startswith("m.") or hostname.startswith("www.m.")):
            raise URLWrapperException("This URL's hostname likely points to a mobile website! ({})".format(hostname))

        path = parsed_url.path
        if Settings.PATH_FILTER and Settings.PATH_FILTER.search(path):
            raise URLWrapperException("This URL's path is filtered! ({})".format(path))

        if path.rstrip("/").split(".")[-1].lower() in Settings.FILTERED_FILE_EXTENSIONS:
            raise URLWrapperException("The file extension of this URL's path is filtered! ({})".format(path))

        if not path.startswith("/"):
            raise URLWrapperException("Invalid URL path! (doesn't start with a slash)")

    def _validate_wikipedia_url(self, hostname: str) -> None:
        # wikipedia hostname formats:
        #  - en.wikipedia.org
        #  - en.m.wikipedia.org

        if not hostname.endswith(".wikipedia.org"):
            return

        # check, if the hostname is pointing to a mobile website and raise exception, if the crawling of mobile webpages is not allowed
        if not Settings.CRAWL_MOBILE_PAGES and hostname.endswith(".m.wikipedia.org"):
            raise URLWrapperException("This hostname is pointing to the mobile variant of Wikipedia! ({})".format(hostname))

        # check allowed language
        if (Settings.ALLOWED_WIKIPEDIA_LANGUAGES is not None) and (not hostname.startswith("www.")):
            for allowed_language in Settings.ALLOWED_WIKIPEDIA_LANGUAGES:
                if hostname.startswith(allowed_language + "."):
                    break
            else:
                raise URLWrapperException("This hostname is pointing to a forbidden Wikipedia language mutation! ({})".format(hostname))

    def _generate_canonical_url(self, parsed_url: urlparse.ParseResult) -> str:
        url = parsed_url.netloc + parsed_url.path
        if parsed_url.query:
            url += "?"
            url += parsed_url.query

        return url
