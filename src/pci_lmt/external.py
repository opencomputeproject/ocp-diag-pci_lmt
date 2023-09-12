# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import socket

from pci_lmt.collector import LmtLaneResult


def send_to_db(_result: LmtLaneResult) -> None:
    pass


def get_host_name() -> str:
    return socket.gethostname()


def get_asset_id() -> str:
    return ""


def get_model_name() -> str:
    return ""
