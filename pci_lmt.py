#!/usr/bin/env fbpython
# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

import argparse
import logging

from .lib import pci_lmt_wrapper
from .utils import common, external


def parse_args() -> argparse.Namespace:
    """Parses given arguments into args dictionary."""
    parser = argparse.ArgumentParser(
        description="Runs Lane Margining Test on PCIe devices."
    )
    parser.add_argument(
        "config_file",
        type=str,
        help="Path to the configuration file (in JSON format).",
        default=None,
    )
    common.add_common_args(parser)

    args = parser.parse_args()
    return args


def main() -> None:
    """Main entry point to run PCIe Lane Margining Test"""
    args = parse_args()

    # Set logging level to ERROR/INFO/DEBUG based on verbose level (0/1/2+).
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.ERROR
        if args.verbose == 0
        else logging.INFO
        if args.verbose == 1
        else logging.DEBUG,
    )

    platform_config = common.get_platform_config_local(args.config_file)
    pci_lmt_wrapper.run_lmt(args=args, platform_config=platform_config, utils=external)


if __name__ == "__main__":
    main()
