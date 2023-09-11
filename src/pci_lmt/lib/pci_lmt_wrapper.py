import json
import logging
import time
from typing import List

from ..utils import common
from . import pci_lmt_lib as lmtlib

logger: logging.Logger = logging.getLogger(__name__)


class PCIe_LMT_Devices:
    def __init__(self, bdf_list):
        self.receiver_number = None
        self.error_count_limit = None
        self.left_right_none = None
        self.up_down = None
        self.steps = None
        self.voltage_or_timing = None
        self.device_list = self.setupDeviceListFromBdfList(bdf_list)

    def setupDeviceListFromBdfList(self, bdf_list):
        device_list = []
        for each in bdf_list:
            device = lmtlib.PCIe_LMT(each)
            device_list.append(device)
        return device_list

    def normalSettingsOnDeviceList(self):
        for device in self.device_list:
            if device.primed:
                for lane in range(device.device_info.width):
                    device.GotoNormalSettings(
                        lane=lane, receiver_number=self.receiver_number
                    )

    def clearErrorLogOnDeviceList(self):
        for device in self.device_list:
            if device.primed:
                for lane in range(device.device_info.width):
                    device.ClearErrorLog(
                        lane=lane, receiver_number=self.receiver_number
                    )

    def noCommandOnDeviceList(self):
        for device in self.device_list:
            if device.primed:
                for lane in range(device.device_info.width):
                    device.NoCommand(lane=lane)

    def infoLaneMarginOnDeviceList(self):  # noqa (FLAKE8) C901
        for device in self.device_list:
            for lane in [0]:
                ret = device.FetchMarginControlCapabilities(
                    lane=lane, receiver_number=self.receiver_number
                )
                if ret["error"] is None:
                    device.primed = True
                    logger.info(
                        "Device %s ReceiverNum %d PRIMED: %s",
                        device.bdf,
                        self.receiver_number,
                        device.device_info,
                    )
                else:
                    logger.warning(
                        "Device %s ReceiverNum %d NOT PRIMED: %s",
                        device.bdf,
                        self.receiver_number,
                        ret["error"],
                    )
                    # Mark all lanes faulty.
                    for lane in range(device.device_info.width):
                        device.lane_errors[lane] = ret["error"]
                    continue

    def setupLaneMarginOnDeviceList(self, error_count_limit=50):
        for device in self.device_list:
            if device.primed:
                for lane in range(device.device_info.width):
                    device.SetErrorCountLimit(
                        lane=lane,
                        receiver_number=self.receiver_number,
                        error_count_limit=self.error_count_limit,
                    )

    def collectLaneMarginOnDeviceList(
        self, voltage_or_timing="TIMING", steps=16, up_down=0, left_right_none=0
    ) -> List[common.LmtLaneResult]:
        """Returns the Lane Margining Test result from all lanes as a list."""
        results = []
        for device in self.device_list:
            # Collect results from all devices and lanes
            # irrespective of device prime or lane error status.
            for lane in range(device.device_info.width):
                lane_result = common.LmtLaneResult(
                    device_info=device.device_info,
                    lane=lane,
                    receiver_number=self.receiver_number,
                    step=steps,
                )
                if voltage_or_timing == "TIMING":
                    lane_result.margin_type = "timing_"
                    if left_right_none == 0:
                        lane_result.margin_type += "right"
                    elif left_right_none == 1:
                        lane_result.margin_type += "left"
                    else:
                        lane_result.margin_type += "none"
                    stepper = device.StepMarginTimingOffsetRightLeftOfDefault(
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
                    stepper = device.StepMarginVoltageOffsetup_downOfDefault(
                        lane=lane,
                        receiver_number=self.receiver_number,
                        up_down=up_down,
                        steps=steps,
                    )

                sampler = device.FetchSampleCount(
                    lane=lane, receiver_number=self.receiver_number
                )
                if stepper["error"] or sampler["error"]:
                    lane_result.error = True
                    lane_result.error_msg = (
                        stepper["error"] if stepper["error"] else sampler["error"]
                    )
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
                    lane_result.ber = (
                        stepper["error_count"] / sampler["sample_count_bits"]
                    )

                results.append(lane_result)

        return results

    # MSampleCount Value = 3*log2 (number of bits margined). The count saturates at 127 (after approximately 5.54 × 1012 bits).

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


def collectLmtOnBDFs(
    hostname,
    asset_id,
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
) -> List[common.LmtLaneResult]:
    # Gather test level info.
    test_info = common.LmtTestInfo()
    test_info.run_id = common.get_run_id()
    test_info.timestamp = common.get_curr_timestamp()
    test_info.asset_id = asset_id
    test_info.hostname = hostname
    test_info.model_name = model_name
    test_info.dwell_time_secs = dwell_time
    test_info.error_count_limit = error_count_limit
    test_info.test_version = common.VERSION
    test_info.annotation = annotation

    logger.info("%s", test_info)
    devices = PCIe_LMT_Devices(bdf_list)

    devices.sampler_setup(
        receiver_number=receiver_number,
        error_count_limit=error_count_limit,
        left_right_none=left_right_none,
        up_down=up_down,
        steps=steps,
        voltage_or_timing=voltage_or_timing,
    )
    devices.noCommandOnDeviceList()
    devices.infoLaneMarginOnDeviceList()
    devices.noCommandOnDeviceList()
    devices.clearErrorLogOnDeviceList()
    devices.normalSettingsOnDeviceList()
    devices.setupLaneMarginOnDeviceList(error_count_limit=devices.error_count_limit)

    start_time = time.time()
    time.sleep(dwell_time)
    results = devices.collectLaneMarginOnDeviceList(
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


def run_lmt(args, platform_config, utils) -> None:
    """Runs LMT tests on all the interfaces listed in the platform_config."""
    hostname = utils.get_host_name()
    asset_id = utils.get_asset_id()
    model_name = utils.get_model_name()
    logger.info("Loading config: %s", json.dumps(platform_config, indent=2))
    csv_header_done = False
    for cfg in platform_config["lmt_groups"]:
        annotation = args.annotation if args.annotation else cfg["name"]
        left_right_none, up_down = common.get_margin_directions(cfg)
        # Loop through each step running LMT on all BDFs.
        for step in cfg["margin_steps"]:
            bdf_list = cfg["bdf_list"]
            margin_type = cfg["margin_type"]
            receiver_number = cfg["receiver_number"]
            logger.info(
                "Running %s margining test on %d BDFs Rx %d Step %d for %d seconds.",
                margin_type,
                len(bdf_list),
                receiver_number,
                step,
                args.dwell_time,
            )
            results = collectLmtOnBDFs(
                hostname=hostname,
                asset_id=asset_id,
                model_name=model_name,
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
                    utils.send_to_db(result)
                elif args.output == "json":
                    print(result.to_json())
                elif args.output == "csv":
                    header, row = result.to_csv()
                    if not csv_header_done:
                        print(header)
                        csv_header_done = True
                    print(row)
                else:
                    raise ValueError("Output must be one of'scribe', 'json', or 'csv'")
