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


from typing import Optional
import sys
import time
import threading
import socket
from Settings import Settings


class Logger:
    _SERVER_LISTEN_BACKLOG: int = 64
    _SOCKET_TRANSFER_ENCODING: str = "utf8"

    _client_sock: Optional[socket.socket] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def start_server(cls) -> None:
        thread = threading.Thread(target=cls._server_thread, daemon=True)
        thread.start()

    @classmethod
    def _server_thread(cls) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((Settings.LOGGER_SOCKET_HOST, Settings.LOGGER_SOCKET_PORT))
            server_sock.listen(cls._SERVER_LISTEN_BACKLOG)

            while True:
                (client_sock, address) = server_sock.accept()

                cls._lock.acquire()
                try:
                    if cls._client_sock:
                        cls._client_sock.close()

                    cls._client_sock = client_sock
                    cls._client_sock.settimeout(Settings.LOGGER_SOCKET_TIMEOUT)

                except OSError:
                    cls._client_sock = None

                finally:
                    cls._lock.release()

    @classmethod
    def log(cls, *args, terminal: bool = False) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        mark = ("!" if terminal else ".")

        args = [str(arg) for arg in args]

        msg = "[{} {}] {}".format(timestamp, mark, " ".join(args))
        msg = msg.replace("\r", "").replace("\n", "")

        cls._lock.acquire()
        try:
            if terminal:
                print(msg, file=sys.stderr)

            cls._write_log_to_socket(msg)

        except OSError:
            try:
                if cls._client_sock:
                    cls._client_sock.close()
            except OSError:
                pass

            cls._client_sock = None

        finally:
            cls._lock.release()

    @classmethod
    def thread_log(cls, thread_id: int, *args, terminal: bool = False) -> None:
        thread_id_str = "[Thread {}]".format(thread_id)
        cls.log(thread_id_str, *args, terminal=terminal)

    @classmethod
    def _write_log_to_socket(cls, msg: str) -> None:
        if cls._client_sock:
            try:
                encoded_msg = (msg + "\r\n").encode(cls._SOCKET_TRANSFER_ENCODING)
            except UnicodeEncodeError:
                return

            cls._client_sock.send(encoded_msg)
