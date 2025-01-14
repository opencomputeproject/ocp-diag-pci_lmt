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
from pci_lmt.config import MarginType, PlatformConfig
from pci_lmt.device import PciDevice
from pci_lmt.host import HostInfo
from pci_lmt.pcie_lane_margining import PcieDeviceLaneMargining
from pci_lmt.results import LmtLaneResult, LmtTestInfo, Reporter

logger: logging.Logger = logging.getLogger(__name__)


class PcieLmCollector:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, test_info: LmtTestInfo, bdf_list: ty.List[str]):
        # TODO: Can use the test_info directly instead of instantiating
        # individual members. But, this change may litter the code. So,
        # will handle this in a separate PR.
        self.receiver_number = test_info.receiver_number
        self.error_count_limit = test_info.error_count_limit
        self.step = test_info.step
        self.margin_type = test_info.margin_type
        self.force_margin = test_info.force_margin
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
            # Collect lane margin capabilties only from lane-0 since it's going to be same
            # for all lanes on that device.
            ret = dev.goto_normal_settings(lane=0, receiver_number=self.receiver_number)
            ret = dev.fetch_margin_control_capabilities(lane=0, receiver_number=self.receiver_number)

            status_str = f"Device {dev.device_info.bdf} ReceiverNum {self.receiver_number} "
            if ret["error"]:
                dev.primed = False
                status_str += f"NOT PRIMED {ret['error']}"
            else:
                # By default, allow devices only with independent error sampler to be primed.
                # Allow devices with no independent error sampler to be primed only if it's forced by user.
                if dev.device_info.ind_error_sampler:
                    dev.primed = True
                    status_str += "PRIMED"
                elif self.force_margin:
                    dev.primed = True
                    status_str += "PRIMED (forcing margin on non-independent sampler)"
                else:
                    dev.primed = False
                    status_str += "NOT PRIMED (doesn't support independent error sampler)"

            if dev.primed:
                logger.info(status_str)
            else:
                logger.warning(status_str)
                # Mark all lanes faulty.
                for lane in range(dev.device_info.width):
                    dev.lane_errors[lane] = status_str

    def setup_lane_margin_on_device_list(self):
        for dev in self._primed_devices:
            for lane in range(dev.device_info.width):
                dev.set_error_count_limit(
                    lane=lane,
                    receiver_number=self.receiver_number,
                    error_count_limit=self.error_count_limit,
                )

                if self.margin_type in (MarginType.TIMING_LEFT, MarginType.TIMING_RIGHT, MarginType.TIMING_NONE):
                    dev.step_margin_timing_offset_right_left_of_default(
                        lane=lane,
                        receiver_number=self.receiver_number,
                        margin_type=self.margin_type,
                        steps=self.step,
                    )
                else:
                    dev.step_margin_voltage_offset_up_down_of_default(
                        lane=lane,
                        receiver_number=self.receiver_number,
                        margin_type=self.margin_type,
                        steps=self.step,
                    )

    def collect_lane_margin_on_device_list(self) -> ty.List[LmtLaneResult]:
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
                    step=self.step,
                    margin_type=self.margin_type.value,
                )

                if self.margin_type in (MarginType.TIMING_LEFT, MarginType.TIMING_RIGHT, MarginType.TIMING_NONE):
                    margin_status = dev.decode_step_margin_timing_offset_right_left_of_default(lane=lane)
                else:
                    margin_status = dev.decode_step_margin_voltage_offset_up_down_of_default(lane=lane)

                sampler = dev.fetch_sample_count(lane=lane, receiver_number=self.receiver_number)
                if margin_status["error"] or sampler["error"]:
                    lane_result.error = True
                    lane_result.error_msg = margin_status["error"] if margin_status["error"] else sampler["error"]
                else:
                    # TODO Check if this needs to be divided by Sampling (aka, 64)
                    lane_result.error = False
                    lane_result.sample_count = sampler["sample_count"]
                    lane_result.sample_count_bits = sampler["sample_count_bits"]
                    lane_result.error_count = margin_status["error_count"]
                    lane_result.ber = margin_status["error_count"] / sampler["sample_count_bits"]

                results.append(lane_result)

        return results


def get_run_id() -> str:
    """Returns an unique ID using RNG."""
    return os.popen("od -N 16 -t uL -An /dev/urandom | sed 's/ //g'").read().split("\n")[0]


def get_curr_timestamp() -> int:
    """Returns the current unix timestamp."""
    return int(os.popen("date +%s").read().split("\n")[0])


def collect_lmt_on_bdfs(test_info: LmtTestInfo, bdf_list: ty.List[str]) -> ty.List[LmtLaneResult]:
    logger.info("%s", test_info)
    devices = PcieLmCollector(test_info, bdf_list)

    devices.no_command_on_device_list()
    devices.info_lane_margin_on_device_list()
    devices.no_command_on_device_list()
    devices.clear_error_log_on_device_list()
    devices.normal_settings_on_device_list()
    devices.setup_lane_margin_on_device_list()

    start_time = time.time()
    time.sleep(test_info.dwell_time_secs)
    results = devices.collect_lane_margin_on_device_list()
    stop_time = time.time()
    test_info.elapsed_time_secs = stop_time - start_time

    # Append test_info to individual results before returning.
    for result in results:
        result.test_info = test_info

    return results


# FIXME: the args param should not be here, arg parsing and usage should be limited to main.py
# instead, replace this with the actual inputs needed; if it's too many, a RuntimeConfig can be made
# pylint: disable=too-many-locals
def run_lmt(
    args: argparse.Namespace, config: PlatformConfig, host: HostInfo, reporter: Reporter
) -> ty.List[LmtLaneResult]:
    """Runs LMT tests on all the interfaces listed in the platform_config."""

    # Caller may do more post-processing on the results.
    # So, gather all results (from individual steps x BDFs x lanes) and return to the caller.
    all_results = []

    logger.info("Loading config: %s", config)
    with reporter.start_run(host):
        test_info = LmtTestInfo()
        test_info.run_id = get_run_id()
        test_info.timestamp = get_curr_timestamp()
        test_info.host_id = host.host_id
        test_info.hostname = host.hostname
        test_info.model_name = host.model_name
        test_info.dwell_time_secs = args.dwell_time
        test_info.error_count_limit = args.error_count_limit
        test_info.force_margin = args.force_margin
        test_info.test_version = PCI_LMT_VERSION
        test_info.config = str(config)

        for group in config.lmt_groups:
            test_info.margin_type = group.margin_type
            test_info.receiver_number = group.receiver_number
            test_info.annotation = args.annotation if args.annotation else group.name

            # Loop through each step running LMT on all BDFs.
            for step in group.margin_steps:
                with reporter.start_step(
                    name=f"Rcvr:{test_info.receiver_number} Step:{step} Ann:{test_info.annotation}"
                ):
                    test_info.step = step
                    results = collect_lmt_on_bdfs(test_info=test_info, bdf_list=group.bdf_list)
                    for result in results:
                        logger.info(result)
                        reporter.write(result)

                    all_results.extend(results)

    return all_results
