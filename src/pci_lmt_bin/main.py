# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import sys
from pathlib import Path

# add the local lib to sys.path for discovery when running from source
sys.path.append(str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
import argparse
import logging
import typing as ty

from pci_lmt import collector
from pci_lmt.args import add_common_args
from pci_lmt.config import read_platform_config
from pci_lmt.host import HostInfo
from pci_lmt.results import AggregatedReporter, CsvStdoutReporter, JsonStdoutReporter, OcptvReporter, Reporter


def parse_args() -> argparse.Namespace:
    """Parses given arguments into args dictionary."""
    parser = argparse.ArgumentParser(description="Runs Lane Margining Test on PCIe devices.")
    parser.add_argument(
        "config_file",
        type=str,
        help="Path to the configuration file (in JSON format).",
        default=None,
    )
    parser.add_argument(
        "-o",
        dest="output",
        type=lambda s: [str(item) for item in s.split(",")],
        help="Output format. Supported formats: json, csv, ocptv. Default: json",
        default="json",
    )
    add_common_args(parser)

    args = parser.parse_args()
    return args


def main() -> None:
    """Main entry point to run PCIe Lane Margining Test"""
    args = parse_args()

    # Set logging level to ERROR/INFO/DEBUG based on verbose level (0/1/2+).
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.ERROR if args.verbose == 0 else logging.INFO if args.verbose == 1 else logging.DEBUG,
    )

    reporters: ty.List[Reporter] = []
    if "json" in args.output:
        reporters.append(JsonStdoutReporter())
    if "csv" in args.output:
        reporters.append(CsvStdoutReporter())
    if "ocptv" in args.output:
        reporters.append(OcptvReporter())

    collector.run_lmt(
        args=args,
        config=read_platform_config(args.config_file),
        host=HostInfo(),
        reporter=AggregatedReporter(reporters),
    )


if __name__ == "__main__":
    main()
