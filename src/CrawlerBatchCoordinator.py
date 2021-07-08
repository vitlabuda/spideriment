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
import threading
import random
from Settings import Settings
from Logger import Logger
from FileTools import FileTools
from CrawlerThread import CrawlerThread
from StopCrawlingException import StopCrawlingException
from CrawledPage import CrawledPage
from URLWrapper import URLWrapper, URLWrapperException
from GlobalVarsHolder import GlobalVarsHolder


class CrawlerBatchCoordinator:
    _ALL_URLS_CRAWLED_ERROR_MESSAGE: str = "All pages in the crawl queue were crawled! There is nothing more to do!"

    def __init__(self, holder: GlobalVarsHolder):
        self._h: GlobalVarsHolder = holder

        self._new_crawled_urls: List[str] = []
        self._new_crawl_queue: List[str] = []
        self._new_crawled_pages_data: List[CrawledPage] = []

    def coordinator_entry(self) -> None:
        Logger.log("Starting to crawl a new batch.")
        self._crawl_batch()
        Logger.log("Crawl batch finished.")

    def _crawl_batch(self) -> None:
        self._remove_already_crawled_pages_from_crawl_queue()

        threads = []
        for thread_id in range(1, Settings.CRAWLER_THREADS + 1):
            batch_crawl_queue = self._get_crawl_queue_for_thread()
            if not batch_crawl_queue:
                break
            thread = self._start_thread(thread_id, batch_crawl_queue)
            threads.append(thread)

        if len(threads) == 0:
            Logger.log(CrawlerBatchCoordinator._ALL_URLS_CRAWLED_ERROR_MESSAGE)
            raise StopCrawlingException(CrawlerBatchCoordinator._ALL_URLS_CRAWLED_ERROR_MESSAGE)

        for thread in threads:
            self._join_thread_and_fetch_data(*thread)

        Logger.log("All threads from this batch finished! (total fetched pages: {}, crawled pages: {}, new URLs in the crawl queue: {})".format(
            len(self._new_crawled_urls),
            len(self._new_crawled_pages_data),
            len(self._new_crawl_queue)
        ))

        self._combine_new_data_with_old_data()
        self._shuffle_and_reduce_crawl_queue_size()
        self._save_new_data()

    def _remove_already_crawled_pages_from_crawl_queue(self) -> None:
        Logger.log("Removing already crawled pages from the crawl queue...")

        # before starting another crawling batch, already crawled urls are removed from the crawl queue
        new_crawl_queue = []
        for i, url_to_crawl in enumerate(self._h.crawl_queue, 1):
            if i % 2500 == 0:  # this can take a long time, so a progress indicator is not a bad thing to have
                Logger.log("Already crawled pages removal progress: {}/{} URLs processed".format(i, len(self._h.crawl_queue)))

            try:
                # first, change the URL to crawl to canonical form, because links in this form are saved in the crawled_urls list
                canonical_url = URLWrapper(url_to_crawl).canonical_url
            except URLWrapperException:
                # if this fails (it shouldn't), don't add currently processed url to the new list and continue
                continue

            if canonical_url in self._h.crawled_urls:
                continue

            new_crawl_queue.append(url_to_crawl)
        self._h.crawl_queue = new_crawl_queue

        Logger.log("Already crawled pages from the crawl queue removed!")

    def _get_crawl_queue_for_thread(self) -> List[str]:
        urls_to_fetch = self._h.crawl_queue[0:Settings.CRAWL_THREAD_BATCH_SIZE]
        del self._h.crawl_queue[0:Settings.CRAWL_THREAD_BATCH_SIZE]

        return urls_to_fetch

    def _start_thread(self, thread_id: int, thread_urls_to_fetch: List[str]) -> Tuple[CrawlerThread, threading.Thread]:
        crawler_thread = CrawlerThread(thread_id, thread_urls_to_fetch, self._h)
        thread = threading.Thread(target=crawler_thread.thread_entry, daemon=True)
        thread.start()

        Logger.log("Started thread with ID {}. (pages to crawl: {})".format(thread_id, len(thread_urls_to_fetch)))

        return crawler_thread, thread

    def _join_thread_and_fetch_data(self, crawler_thread: CrawlerThread, thread: threading.Thread) -> None:
        Logger.log("Waiting for thread with ID {} to finish...".format(crawler_thread.thread_id))

        thread.join()
        # new_crawled_urls is "fetched pages" in the log, since this variable also contains pages that could not be crawled
        Logger.log("Thread with ID {} finished! (fetched pages: {}, crawled pages: {}, new URLs in the crawl queue: {})".format(
            crawler_thread.thread_id,
            len(crawler_thread.new_crawled_urls),
            len(crawler_thread.crawled_pages_data),
            len(crawler_thread.new_crawl_queue)
        ))

        self._new_crawled_urls += crawler_thread.new_crawled_urls
        self._new_crawl_queue += crawler_thread.new_crawl_queue
        self._new_crawled_pages_data += crawler_thread.crawled_pages_data

        Logger.log("New data from the finished thread were exported !")

    def _combine_new_data_with_old_data(self) -> None:
        Logger.log("Removing duplicates from the new crawled data...")

        # before combining, check if any of the crawled pages...
        unique_pages = []
        for crawled_page in self._new_crawled_pages_data:
            # ... was crawled more times than one (can happen due to redirects)
            if self._check_if_page_was_crawled_more_times(crawled_page):
                continue
            # ... was already crawled in previous batches (can happen due to redirects)
            if crawled_page.original_url.canonical_url in self._h.crawled_urls or crawled_page.final_url.canonical_url in self._h.crawled_urls:
                continue
            unique_pages.append(crawled_page)
        self._new_crawled_pages_data = unique_pages

        Logger.log("Duplicates removed, combining the new crawled data with the old data...")

        # converting to set(), combining those two sets and then converting back to list() ensures uniqueness of all the data
        self._h.crawled_urls = list(set(self._h.crawled_urls) | set(self._new_crawled_urls))
        self._h.crawl_queue = list(set(self._h.crawl_queue) | set(self._new_crawl_queue))
        del self._new_crawled_urls, self._new_crawl_queue  # save memory

        Logger.log("The new crawled data were combined with the old data!")

    def _check_if_page_was_crawled_more_times(self, crawled_page: CrawledPage) -> bool:
        # used in self._combine_new_data_with_old_data (convenience method to make continuing an outer loop easier)
        count = 0
        for crawled_page_ in self._new_crawled_pages_data:
            if crawled_page.original_url.canonical_url == crawled_page_.original_url.canonical_url or crawled_page.final_url.canonical_url == crawled_page_.final_url.canonical_url:
                count += 1

        if count == 1:
            return False
        return True

    def _shuffle_and_reduce_crawl_queue_size(self) -> None:
        Logger.log("Shuffling the crawl queue...")

        # shuffle the list, so there is a wider variety of the crawled pages; it's done before reducing the size (although it would perform better),
        #  because there is a bigger set of data to shuffle (which increases the randomness)
        random.shuffle(self._h.crawl_queue)

        Logger.log("Shuffling done, reducing the crawl queue size...")

        # this list gets often huge, so to speed up the iterations etc. (such as in CrawledPage._count_links_already_present_in_list),
        #   it's a good idea to reduce the list's size to something sensible
        self._h.crawl_queue = self._h.crawl_queue[0:Settings.MAX_CRAWL_QUEUE_SIZE]

        Logger.log("The crawl queue size was reduced!")

    def _save_new_data(self) -> None:
        Logger.log("Saving new data...")

        page_data_json = [crawled_page.to_json() for crawled_page in self._new_crawled_pages_data]

        Logger.log("Saved data stats: crawled URLs = {}, crawl queue = {}, crawled pages = {}".format(
            len(self._h.crawled_urls),
            len(self._h.crawl_queue),
            len(page_data_json)
        ))

        FileTools(Settings.CRAWLED_URLS_FILE).write_iterable_to_csv(self._h.crawled_urls)
        FileTools(Settings.CRAWL_QUEUE_FILE).write_iterable_to_csv(self._h.crawl_queue)
        FileTools(Settings.WEB_INDEX_FILE).append_iterable_to_csv(page_data_json)

        Logger.log("New data saved!")
