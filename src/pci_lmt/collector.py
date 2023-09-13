# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import argparse
import logging
import os
import time
import typing as ty

from pci_lmt import __version__ as PCI_LMT_VERSION
from pci_lmt.config import PlatformConfig
from pci_lmt.device import PciDevice
from pci_lmt.host import HostInfo
from pci_lmt.pcie_lane_margining import PcieDeviceLaneMargining
from pci_lmt.results import LmtLaneResult, LmtTestInfo, Reporter

logger: logging.Logger = logging.getLogger(__name__)


class PcieLmCollector:
    def __init__(self, bdf_list: ty.List[str]):
        self.receiver_number = None
        self.error_count_limit = None
        self.left_right_none = None
        self.up_down = None
        self.steps = None
        self.voltage_or_timing = None
        self.devices = [PcieDeviceLaneMargining(PciDevice(bdf)) for bdf in bdf_list]

    @property
    def _primed_devices(self) -> ty.Generator[PcieDeviceLaneMargining, None, None]:
        for dev in self.devices:
            if not dev.primed:
                continue
            yield dev

    def normal_settings_on_device_list(self):
        for dev in self._primed_devices:
            for lane in range(dev.device_info.width):
                dev.goto_normal_settings(lane=lane, receiver_number=self.receiver_number)

    def clear_error_log_on_device_list(self):
        for dev in self._primed_devices:
            for lane in range(dev.device_info.width):
                dev.clear_error_log(lane=lane, receiver_number=self.receiver_number)

    def no_command_on_device_list(self):
        for dev in self._primed_devices:
            for lane in range(dev.device_info.width):
                dev.no_command(lane=lane)

    def info_lane_margin_on_device_list(self):
        for dev in self.devices:
            for lane in [0]:
                ret = dev.fetch_margin_control_capabilities(lane=lane, receiver_number=self.receiver_number)
                if ret["error"] is None:
                    dev.primed = True
                    logger.info(
                        "Device %s ReceiverNum %d PRIMED: %s",
                        dev.device_info.bdf,
                        self.receiver_number,
                        dev.device_info,
                    )
                    continue

                logger.warning(
                    "Device %s ReceiverNum %d NOT PRIMED: %s",
                    dev.device_info.bdf,
                    self.receiver_number,
                    ret["error"],
                )
                # Mark all lanes faulty.
                for lane in range(dev.device_info.width):
                    dev.lane_errors[lane] = ret["error"]

    def setup_lane_margin_on_device_list(self):
        for dev in self._primed_devices:
            for lane in range(dev.device_info.width):
                dev.set_error_count_limit(
                    lane=lane,
                    receiver_number=self.receiver_number,
                    error_count_limit=self.error_count_limit,
                )

    # FIXME: `voltage_or_timing` should be an enum; dont use strings for magic constants
    # pylint: disable=too-many-branches
    def collect_lane_margin_on_device_list(
        self, voltage_or_timing="TIMING", steps=16, up_down=0, left_right_none=0
    ) -> ty.List[LmtLaneResult]:
        """Returns the Lane Margining Test result from all lanes as a list."""
        results = []
        for dev in self.devices:
            # Collect results from all devices and lanes
            # irrespective of device prime or lane error status.
            for lane in range(dev.device_info.width):
                lane_result = LmtLaneResult(
                    device_info=dev.device_info,
                    lane=lane,
                    receiver_number=ty.cast(int, self.receiver_number),
                    step=steps,
                )
                if voltage_or_timing == "TIMING":
                    # FIXME: move this string construction in a separate method; or better make it
                    # into a typed enum
                    lane_result.margin_type = "timing_"
                    if left_right_none == 0:
                        lane_result.margin_type += "right"
                    elif left_right_none == 1:
                        lane_result.margin_type += "left"
                    else:
                        lane_result.margin_type += "none"
                    stepper = dev.step_margin_timing_offset_right_left_of_default(
                        lane=lane,
                        receiver_number=self.receiver_number,
                        left_right_none=left_right_none,
                        steps=steps,
                    )

                if voltage_or_timing == "VOLTAGE":
                    lane_result.margin_type = "voltage_"
                    if up_down == 0:
                        lane_result.margin_type += "up"
                    elif up_down == 1:
                        lane_result.margin_type += "down"
                    else:
                        lane_result.margin_type += "none"
                    stepper = dev.step_margin_voltage_offset_up_down_of_default(
                        lane=lane,
                        receiver_number=self.receiver_number,
                        up_down=up_down,
                        steps=steps,
                    )

                sampler = dev.fetch_sample_count(lane=lane, receiver_number=self.receiver_number)
                if stepper["error"] or sampler["error"]:
                    lane_result.error = True
                    lane_result.error_msg = stepper["error"] if stepper["error"] else sampler["error"]
                elif stepper["error_count"] == 0:
                    lane_result.error = False
                    lane_result.sample_count = sampler["sample_count"]
                    lane_result.sample_count_bits = sampler["sample_count_bits"]
                    lane_result.error_count = 0
                    lane_result.ber = 0.0
                else:
                    # TODO Check if this needs to be divided by Sampling (aka, 64)
                    lane_result.error = False
                    lane_result.sample_count = sampler["sample_count"]
                    lane_result.sample_count_bits = sampler["sample_count_bits"]
                    lane_result.error_count = stepper["error_count"]
                    lane_result.ber = stepper["error_count"] / sampler["sample_count_bits"]

                results.append(lane_result)

        return results

    # MSampleCount Value = 3*log2 (number of bits margined). The count saturates at 127
    # (after approximately 5.54 × 1012 bits).

    # FIXME: why isnt this part of __init__?
    # pylint: disable=too-many-arguments
    def sampler_setup(
        self,
        receiver_number=0x1,
        error_count_limit=50,
        left_right_none=0,
        up_down=0,
        steps=16,
        voltage_or_timing="TIMING",
    ):
        self.receiver_number = receiver_number
        self.error_count_limit = error_count_limit
        self.left_right_none = left_right_none
        self.up_down = up_down
        self.steps = steps
        self.voltage_or_timing = voltage_or_timing


def get_run_id() -> str:
    """Returns an unique ID using RNG."""
    return os.popen("od -N 16 -t uL -An /dev/urandom | sed 's/ //g'").read().split("\n")[0]


def get_curr_timestamp() -> int:
    """Returns the current unix timestamp."""
    return int(os.popen("date +%s").read().split("\n")[0])


# pylint: disable=too-many-arguments,too-many-locals
def collect_lmt_on_bdfs(
    hostname,
    host_id,
    model_name,
    bdf_list,
    receiver_number: int = 0x1,
    error_count_limit: int = 50,
    left_right_none: int = 0,
    up_down=None,
    steps: int = 13,
    voltage_or_timing: str = "TIMING",
    dwell_time: int = 5,
    annotation: str = "",
) -> ty.List[LmtLaneResult]:
    # Gather test level info.
    test_info = LmtTestInfo()
    test_info.run_id = get_run_id()
    test_info.timestamp = get_curr_timestamp()
    test_info.host_id = host_id
    test_info.hostname = hostname
    test_info.model_name = model_name
    test_info.dwell_time_secs = dwell_time
    test_info.error_count_limit = error_count_limit
    test_info.test_version = PCI_LMT_VERSION
    test_info.annotation = annotation

    logger.info("%s", test_info)
    devices = PcieLmCollector(bdf_list)

    devices.sampler_setup(
        receiver_number=receiver_number,
        error_count_limit=error_count_limit,
        left_right_none=left_right_none,
        up_down=up_down,
        steps=steps,
        voltage_or_timing=voltage_or_timing,
    )
    devices.no_command_on_device_list()
    devices.info_lane_margin_on_device_list()
    devices.no_command_on_device_list()
    devices.clear_error_log_on_device_list()
    devices.normal_settings_on_device_list()
    devices.setup_lane_margin_on_device_list()

    start_time = time.time()
    time.sleep(dwell_time)
    results = devices.collect_lane_margin_on_device_list(
        voltage_or_timing=devices.voltage_or_timing,
        steps=devices.steps,
        up_down=devices.up_down,
        left_right_none=devices.left_right_none,
    )
    stop_time = time.time()
    test_info.elapsed_time_secs = stop_time - start_time

    # Append test_info to individual results before returning.
    for result in results:
        result.test_info = test_info

    return results


# pylint: disable=too-many-locals
def run_lmt(args: argparse.Namespace, config: PlatformConfig, host: HostInfo, reporter: Reporter) -> None:
    """Runs LMT tests on all the interfaces listed in the platform_config."""

    logger.info("Loading config: %s", config)
    csv_header_done = False

    for group in config.lmt_groups:
        annotation = args.annotation if args.annotation else group.name
        left_right_none, up_down = group.margin_directions_tuple
        # Loop through each step running LMT on all BDFs.
        for step in group.margin_steps:
            bdf_list = group.bdf_list
            margin_type = group.margin_type
            receiver_number = group.receiver_number
            logger.info(
                "Running %s margining test on %d BDFs Rx %d Step %d for %d seconds.",
                margin_type,
                len(bdf_list),
                receiver_number,
                step,
                args.dwell_time,
            )
            results = collect_lmt_on_bdfs(
                hostname=host.hostname,
                host_id=host.host_id,
                model_name=host.model_name,
                bdf_list=bdf_list,
                receiver_number=receiver_number,
                error_count_limit=args.error_count_limit,
                left_right_none=left_right_none,
                up_down=up_down,
                steps=step,
                voltage_or_timing=margin_type,
                dwell_time=args.dwell_time,
                annotation=annotation,
            )
            for result in results:
                logger.info(result)
                if args.output == "scribe":
                    reporter.write(result)
                elif args.output == "json":
                    print(result.to_json())
                elif args.output == "csv":
                    header, row = result.to_csv()
                    if not csv_header_done:
                        print(header)
                        csv_header_done = True
                    print(row)
                else:
                    raise ValueError("Output must be one of 'scribe', 'json', or 'csv'")
