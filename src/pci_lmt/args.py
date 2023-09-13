# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import argparse

from pci_lmt import __version__ as PCI_LMT_VERSION


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Adds common CLI args to the given parser."""

    parser.add_argument(
        "-e",
        dest="error_count_limit",
        type=int,
        help="Maximum errors allowed before terminating the test. Default: 63",
        default=63,
    )
    parser.add_argument(
        "-d",
        dest="dwell_time",
        type=int,
        help="Amount of time (in seconds) to wait before making BER measurements. Default: 5",
        default=5,
    )
    parser.add_argument(
        "-a",
        dest="annotation",
        type=str,
        help="Annotation string to be prefix'd for LMT results. Default: <empty>",
        default="",
    )
    parser.add_argument(
        "-v",
        dest="verbose",
        action="count",
        help="Verbosity level. Use '-v' for INFO and '-vv' for DEBUG. Default: 0",
        default=0,
    )
    parser.add_argument(
        "--version",
        action="version",
        help="Print tool version and exit.",
        version="%(prog)s " + PCI_LMT_VERSION,
    )
