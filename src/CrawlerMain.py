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


from typing import Tuple, List
import sys
import time
import signal
import gc
from Settings import Settings
from Logger import Logger
from FileTools import FileTools
from CrawlerBatchCoordinator import CrawlerBatchCoordinator
from StopCrawlingException import StopCrawlingException
from GlobalVarsHolder import GlobalVarsHolder


class CrawlerMain:
    def __init__(self):
        self._perform_basic_initialization()

        crawled_urls, crawl_queue = self._load_saved_crawled_urls_and_crawl_queue()

        self._continue_running: bool = True
        self._h: GlobalVarsHolder = GlobalVarsHolder(crawled_urls, crawl_queue)

    def start(self) -> None:
        self._start_timeout()
        Logger.log("Starting crawler.", terminal=True)

        self._main_loop()

        self._exit()

    def _perform_basic_initialization(self) -> None:
        Settings.initialize_settings()
        Logger.start_server()
        Settings.create_directories()
        self._set_signal_handlers()

        Logger.log("Basic initialization performed.")

    def _set_signal_handlers(self) -> None:
        for signum in Settings.CAPTURED_SIGNALS:
            signal.signal(signum, self._signal_handler)

            # restart system calls if a signal is received (so the program can finish gracefully without any semi-predictable state changes)
            signal.siginterrupt(signum, False)

    def _signal_handler(self, signum, frame) -> None:
        self._continue_running = False
        Logger.log("A signal requested the program to exit. Please wait for the current batch to finish.", terminal=True)

    def _load_saved_crawled_urls_and_crawl_queue(self) -> Tuple[List[str], List[str]]:
        Logger.log("Loading saved crawled URLs and crawl queue.")

        crawled_urls: List[str] = FileTools(Settings.CRAWLED_URLS_FILE).read_1d_csv_to_list()
        crawl_queue: List[str] = FileTools(Settings.CRAWL_QUEUE_FILE).read_1d_csv_to_list()
        if len(crawl_queue) == 0:  # if the crawl queue is empty, use the start urls
            Logger.log("The crawl queue is empty, using the default start URLs.")
            crawl_queue = list(Settings.START_URLS)

        Logger.log("Crawled URLs ({}) and crawl queue ({}) loaded!".format(len(crawled_urls), len(crawl_queue)))

        return crawled_urls, crawl_queue

    def _start_timeout(self) -> None:
        seconds = Settings.CRAWLER_START_TIMEOUT
        while seconds > 0:
            Logger.log("Crawler starting in {} second(s)...".format(seconds))
            time.sleep(1)
            seconds -= 1

    def _main_loop(self) -> None:
        try:
            while self._continue_running:
                self._inner_main_loop()

        except StopCrawlingException as e:
            Logger.log("The program wants to exit:", str(e), terminal=True)

    def _inner_main_loop(self) -> None:
        coordinator = CrawlerBatchCoordinator(self._h)
        coordinator.coordinator_entry()

        # destroy all unnecessary data before starting another batch
        del coordinator
        gc.collect()

    def _exit(self) -> None:
        Logger.log("Exiting crawler.", terminal=True)
        sys.exit(0)
