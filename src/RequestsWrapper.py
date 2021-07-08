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
from typing import Optional, Union, Tuple, Dict
from collections import Iterable
import requests
import urllib3
from requests.structures import CaseInsensitiveDict
from Settings import Settings
from URLWrapper import URLWrapper, URLWrapperException


class RequestsWrapperException(Exception):
    pass


class RequestsWrapper:
    class FetchedFile:
        def __init__(self, status_code: int, text: str, final_url: str, original_url: str, headers: CaseInsensitiveDict):
            self.status_code: int = status_code
            self.text: str = text

            try:
                self.final_url: URLWrapper = URLWrapper(final_url)
                self.original_url: URLWrapper = URLWrapper(original_url)
            except URLWrapperException as e:
                raise RequestsWrapperException("The fetched file's URL was invalid: " + str(e))

            self.headers: CaseInsensitiveDict = headers

    _REQUEST_HEADERS: Dict[str, str] = {
        "Connection": "close",
        "User-Agent": Settings.USER_AGENT
    }
    _FETCH_CHUNK_SIZE: int = 65536

    def __init__(self, url: str, allowed_content_type: Optional[Union[str, Iterable]], max_fetch_size: int):
        self._url: str = url
        self._allowed_content_type: Optional[Union[str, Iterable]] = allowed_content_type
        self._max_fetch_size: int = max_fetch_size

        # those variables can get changed from the outside, if needed
        self.fail_on_bigger_size: bool = False
        self.fail_on_non_200_status_code: bool = True

    @classmethod
    def from_url_wrapper(cls, url_wrapper: URLWrapper, allowed_content_type: Optional[Union[str, Iterable]], max_fetch_size: int) -> RequestsWrapper:
        return cls(url_wrapper.url, allowed_content_type, max_fetch_size)

    def fetch_with_metadata(self) -> FetchedFile:  # returns str if self.dont_check_urls_and_return_text_only is true (used when fetching robots.txt)
        response, text = self._generic_fetch()

        return RequestsWrapper.FetchedFile(response.status_code, text, response.url, self._url, response.headers)

    # this method also skips URL check since it doesn't instantiate the FetchedFile class -> used for fetching robots.txt
    #  (since .txt file extension may be filtered, although it's perfectly valid for robots.txt)
    def fetch_text_only_and_skip_url_check(self) -> str:
        _, text = self._generic_fetch()

        return text

    def _generic_fetch(self) -> Tuple[requests.Response, str]:
        (response, data) = self._download_data_from_server()

        if self.fail_on_non_200_status_code and response.status_code != 200:
            raise RequestsWrapperException(
                "The server responded with a non-200 status code! ({})".format(response.status_code))

        self._check_content_type(response.headers)

        text = self._decode_data(data)
        del data  # to save some memory

        return response, text

    def _download_data_from_server(self) -> Tuple[requests.Response, bytes]:
        r = None
        try:
            r = requests.get(self._url,
                             timeout=Settings.HTTP_REQUEST_TIMEOUT,
                             stream=True,
                             allow_redirects=True,
                             headers=RequestsWrapper._REQUEST_HEADERS,
                             proxies=Settings.PROXIES)

            data = b''
            while True:
                chunk = r.raw.read(RequestsWrapper._FETCH_CHUNK_SIZE, decode_content=True)
                if not chunk:
                    break
                data += chunk
                if len(data) > self._max_fetch_size:
                    if self.fail_on_bigger_size:
                        raise RequestsWrapperException("The size of this page is too big! (at least {} bytes)".format(len(data)))
                    break

            return r, data

        except (requests.RequestException, urllib3.exceptions.HTTPError, UnicodeError) as e:
            raise RequestsWrapperException("Failed to fetch a page: {}".format(str(e)))
        finally:
            if r:
                r.raw.close()

    def _decode_data(self, data: bytes) -> str:
        # according to https://w3techs.com/technologies/overview/character_encoding (as of January 2021):
        # - most used encoding on the web: utf8
        # - second most used encoding: latin1 (iso-8859-1)

        try:
            return data.decode("utf8")
        except UnicodeDecodeError:
            pass

        # shouldn't ever fail, as python can decode all 256 possible latin1 byte values
        return data.decode("latin1")

    def _check_content_type(self, headers: CaseInsensitiveDict) -> None:
        if self._allowed_content_type is None:
            return

        if "Content-Type" not in headers:
            raise RequestsWrapperException("Content-Type is not in HTTP response headers!")

        content_type = headers["Content-Type"].lower()
        if isinstance(self._allowed_content_type, str):
            # using "in" instead of "==", because the received header might contain charset etc.
            if self._allowed_content_type.lower() not in content_type:
                raise RequestsWrapperException("Content-Type \"{}\" not allowed!".format(content_type))
        else:
            for allowed_type in self._allowed_content_type:
                if allowed_type.lower() in content_type:
                    break
            else:
                raise RequestsWrapperException("Content-Type \"{}\" not allowed!".format(content_type))
