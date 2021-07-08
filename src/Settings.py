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


from typing import Dict, Optional, Tuple
import os
import os.path
import re
import signal


_APP_VERSION: str = "1.0"
_SPIDERIMENT_SAVEDATA_DIR: str = os.path.join(os.path.dirname(os.path.realpath(__file__)), "spideriment_savedata/")


class Settings:
    APP_VERSION: str = _APP_VERSION

    CRAWLER_START_TIMEOUT: int = 5  # Useful when you want to connect to the log socket before the crawler starts; set to 0 if you don't want any timeout.
    CAPTURED_SIGNALS: tuple = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)

    # To avoid getting on abuse IP lists, it's a very good idea to route the traffic through Tor.
    PROXIES: Dict[str, str] = {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050"
    }

    # The program sends log messages to a client connected to this plaintext socket. You can use netcat or telnet to connect to it.
    LOGGER_SOCKET_HOST: str = "127.0.0.1"  # It's highly recommended to keep the logger socket localhost-only, as it doesn't have any authentication!
    LOGGER_SOCKET_PORT: int = 5566
    LOGGER_SOCKET_TIMEOUT: int = 3

    USER_AGENT: str = "Mozilla/5.0 (X11; Linux x86_64) Spideriment/{} (web spider; respects robots.txt disallows)".format(_APP_VERSION)
    ROBOTS_TXT_USER_AGENT: str = "Spideriment"

    # You usually don't want to crawl those things:
    #  - hidden services (.onion)
    #  - websites related to government (the crawler can contain bugs and there are certainly better ways to test it than on govt websites)
    #  - archived webpages
    #  - websites with a lot of local links where the crawler can easily "get stuck"
    HOSTNAME_FILTER: Optional[re.Pattern] = re.compile(r'\.onion$|\.mil$|\.gov$|gov\.[a-z]+$|archive\.org$|ozmovies\.com\.au$|patents\.google\.com$', re.IGNORECASE)  # webpage is not crawled if its URL's hostname matches this regex
    PATH_FILTER: Optional[re.Pattern] = None  # webpage is not crawled if its URL's path matches this regex
    CRAWL_MOBILE_PAGES: bool = False

    # Non-html files won't parsed anyway; this is only there to filter unnecessary file downloads if the extension is specified in the URL.
    #  All filtered file extensions must be lowercase!
    FILTERED_FILE_EXTENSIONS: Tuple[str, ...] = ("jpg", "jpeg", "bmp", "gif", "png", "tif", "tiff", "svg", "heic", "heif", "ico",
                                                 "raw", "xcf", "psd", "zps", "cdr", "mp3", "wav", "wma", "flac", "ogg", "aac",
                                                 "m4a", "mp4", "avi", "wmv", "flv", "webm", "mkv", "3gp", "m4v", "mov", "zip",
                                                 "rar", "7z", "tar", "gz", "bz2", "xz", "z", "tgz", "tbz2", "txz", "tz", "ggb",
                                                 "pdf", "tex", "doc", "docx", "docm", "rtf", "odt", "xls", "xlsx", "xlsm", "txt",
                                                 "ods", "ppt", "pptx", "pptm", "odp", "sql", "log", "csv", "tsv", "json", "iso",
                                                 "img", "vmdk", "qcow", "qcow2", "scr", "bin", "exe", "vbs", "app", "msi", "msu",
                                                 "cab", "dmg", "rpm", "deb", "pkg", "appimage", "apk", "bat", "cmd", "sh", "bash",
                                                 "dll", "so", "ko", "ini", "cfg", "cnf", "conf", "cur", "ani", "lnk", "sys",
                                                 "drv", "pak", "tmp", "bak", "dmp")

    # Set to None if you want to crawl pages in all languages.
    #  Languages will be checked case-insensitively and with the "in" operator (no need to enter e.g. "en-US", since "en" will work too).
    #  In case the HTML document won't have any "lang" attribute, the page will be crawled.
    ALLOWED_LANGUAGES: Optional[Tuple[str, ...]] = (
        "en", "US", "GB",  # "en" will work in most cases, "US" & "GB" are there `just in case`
        "cs", "CZ",  # same as above
        # "sk",
        # "de"
    )
    ALLOWED_WIKIPEDIA_LANGUAGES: Optional[Tuple[str, ...]] = ("en", "cs")  # Set to None if you want to crawl all Wikipedia language mutations.

    # Some pages use non-standard implementation of robots.txt which prevents the crawler from fetching them (although they are completely legit to fetch).
    #  This directive is used to define an exception list - all URLs (in their canonical form - see URLWrapper) specified there will skip the robots.txt check and pass it automatically.
    #  It doesn't have any effect on the robots meta tag.
    ROBOTS_TXT_ALWAYS_ALLOW_URLS: tuple = tuple()

    # Limits & sizes
    # These values are ideal for Intel Celeron J1800 CPU with 2GB RAM.
    MAX_PAGE_FETCH_SIZE: int = 1000000  # ~ 1 MB
    MAX_ROBOTS_FETCH_SIZE: int = 60000  # ~ 60 kB
    MAX_ROBOTS_CACHE_ENTRIES: int = 60000  # stored in RAM
    MAX_CRAWL_QUEUE_SIZE: int = 25000
    HTTP_REQUEST_TIMEOUT = 10
    CRAWLER_THREADS: int = 15
    CRAWL_THREAD_BATCH_SIZE: int = 250

    URL_MAX_LENGTH: int = 1000
    PAGE_TITLE_MAX_LENGTH: int = 250
    PAGE_HTML_HEADING_MAX_LENGTH: int = 75
    PAGE_HTML_HEADING_MAX_LEVEL: int = 4  # only h1, h2, h3 and h4 headings are saved
    PAGE_MAX_HTML_HEADINGS_PER_LEVEL: int = 5
    PAGE_DESCRIPTION_MAX_LENGTH: int = 300
    PAGE_KEYWORDS_MAX_LENGTH: int = 100
    PAGE_AUTHOR_MAX_LENGTH: int = 50
    PAGE_CONTENT_SNIPPET_MAX_LENGTH: int = 2250
    PAGE_IMAGE_ALTS_MAX_LENGTH: int = 125
    PAGE_LINK_TEXTS_MAX_LENGTH: int = 225
    PAGE_MAX_CRAWLED_LINKS_PER_WEBPAGE: int = 100

    # When links are extracted from a crawled webpage, the links will be checked against the local robots.txt cache (no new robots.txt files will be fetched at this point).
    # Having it enabled may slow down the crawling process, but it will make the crawl queue somewhat cleaner.
    PRECHECK_ROBOTS_ALLOWANCE_OF_CRAWLED_LINKS: bool = True

    START_URLS: Tuple[str, ...] = (
        "https://cs.wikipedia.org/wiki/Hlavn%C3%AD_strana",
        "https://en.wikipedia.org/wiki/Main_Page",
        "https://www.seznam.cz/",
        "https://www.idnes.cz/",
        "https://www.root.cz/",
        "https://www.google.cz/",
        "https://www.google.com/",
        "https://www.youtube.com/"
    )

    # Save files
    CRAWLED_URLS_FILE: str = os.path.join(_SPIDERIMENT_SAVEDATA_DIR, "crawled_urls.csv")  # Used by the program to restore its state - you probably won't be interested in this file.
    CRAWL_QUEUE_FILE: str = os.path.join(_SPIDERIMENT_SAVEDATA_DIR, "crawl_queue.csv")  # Used by the program to restore its state - you probably won't be interested in this file.
    WEB_INDEX_FILE: str = os.path.join(_SPIDERIMENT_SAVEDATA_DIR, "web_index.csv")  # The web index - this is what you want.

    @staticmethod
    def initialize_settings() -> None:
        # Circular import prevention
        from URLWrapper import URLWrapper

        always_allow_urls = []
        for always_allow_url in Settings.ROBOTS_TXT_ALWAYS_ALLOW_URLS:
            always_allow_urls.append(URLWrapper(always_allow_url))
        Settings.ROBOTS_TXT_ALWAYS_ALLOW_URLS = tuple(always_allow_urls)

    @staticmethod
    def create_directories() -> None:
        os.makedirs(_SPIDERIMENT_SAVEDATA_DIR, exist_ok=True)
