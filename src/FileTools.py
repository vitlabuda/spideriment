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


from typing import List, Set
from collections import Iterable
import os
import csv


class FileTools:
    def __init__(self, filepath: str):
        self._filepath: str = filepath

    def read_1d_csv_to_list(self, must_exist: bool = False) -> List[str]:
        data = []

        if must_exist or os.path.exists(self._filepath):
            with open(self._filepath) as csv_file:
                reader = csv.reader(csv_file)
                for line in reader:
                    data.append(line[0])

        return data

    def read_1d_csv_to_set(self, must_exist: bool = False) -> Set[str]:
        return set(self.read_1d_csv_to_list(must_exist))

    # the iterable is 1D, but it's converted to csv anyway due to possible newlines etc.
    def _iterable_to_csv_file(self, open_mode: str, data: Iterable) -> None:
        with open(self._filepath, open_mode) as csv_file:
            writer = csv.writer(csv_file)
            for item in data:
                writer.writerow((item,))

    def write_iterable_to_csv(self, data: Iterable) -> None:
        self._iterable_to_csv_file("w", data)

    def append_iterable_to_csv(self, data: Iterable) -> None:
        self._iterable_to_csv_file("a", data)
