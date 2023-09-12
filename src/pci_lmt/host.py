# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import socket


class HostInfo:
    """
    Provides details about the current host running the LMT binary.
    """

    @property
    def hostname(self) -> str:
        return socket.gethostname()

    @property
    def host_id(self) -> str:
        return ""

    @property
    def model_name(self) -> str:
        return ""
