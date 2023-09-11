# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import logging
import time

from ..utils import common
from . import pci_lib as pcilib
from .constants import MARGIN_RESPONSE, PARAMETERS

logger: logging.Logger = logging.getLogger(__name__)

CAPABILITIES_POINTER = 0x34
TIMEOUT = 0.5  # seconds


# Decorator function to check the lane_errors status prior performing any
# operations and update lane_errors status accordingly.
def handle_lane_status(function_call):
    def wrapper(self, lane: int, *args, **kwargs):
        # Skip invoking the function if the device is faulty.
        if self.device_error is not None:
            return {"error": self.device_error}

        # Skip invoking the function if the lane is already faulty.
        # Return the first error encountered.
        if self.lane_errors[lane] is not None:
            return {"error": self.lane_errors[lane]}

        # Invoke the function and update the lane_errors if the function failed.
        ret = function_call(self, lane, *args, **kwargs)
        if ret["error"] is not None:
            logger.warning(f"{function_call} failed for BDF {self.bdf} lane {lane}: {ret['error']}")
            self.lane_errors[lane] = ret["error"]
        return ret

    return wrapper


class PCIe_LMT:
    def __init__(self, bdf):
        self.pcilib = pcilib.PciLib(bdf)
        self.device_info = common.LmtDeviceInfo()
        self.bdf = bdf
        self.device_info.bdf = bdf
        self.primed = False

        # Placeholder to store the device error status.
        # This is checked in each function call (via handle_lane_status decorator).
        self.device_error = None

        link_status = self.pcilib.get_link_status()
        if link_status.err_msg:
            self.device_error = f"BDF {self.bdf} Link down or device not present: {link_status.err_msg}"
            return

        if link_status.width not in (1, 2, 4, 8, 16, 32, 64):
            self.device_error = f"BDF {self.bdf} Unsupported Link width {link_status.width}"
            return
        self.device_info.width = link_status.width

        if link_status.speed_gts not in ("16GT/s", "32GT/s", "64GT/s"):
            self.device_error = f"BDF:{self.bdf} Unsupported link speed {link_status.speed_gts}"
            return
        self.device_info.speed = link_status.speed_gts

        lmt_cap_info = self.pcilib.get_lmt_cap_info()
        if lmt_cap_info.err_msg:
            self.device_error = f"BDF: {self.bdf} Lane Margining unsupported {lmt_cap_info.err_msg}"
            return
        self.CAP_LMT_OFFSET = lmt_cap_info.offset

        # Place holder to store the errors encountered on each lane.
        # This is checked in each function call (via handle_lane_status decorator).
        self.lane_errors = [None] * self.device_info.width

    @handle_lane_status
    def write_MarginingLaneControlRegister(
        self,
        lane=0,
        receiver_number=0x0,
        margin_type=0x7,
        usage_model=0x0,
        margin_payload=0x9C,
    ):
        address = 0x8 + (lane * 0x4)
        data = self.pcilib.read(address=self.CAP_LMT_OFFSET + address, width=16)
        if data == -1:
            return {"error": "ERROR: write_MarginingLaneControlRegister - read"}
        else:
            # bit 7 is reserved so reading it and writing it back the same.
            data = data & 0x0080
            # Receiver Number. – See Section 8.4.4 for details. The default value is 000b.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            data = data | ((receiver_number & 0x7) << 0)  # 2:0
            # Margin Type –See Section 8.4.4 for details. The default value is 111b.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            data = data | ((margin_type & 0x7) << 3)  # 5:3
            # Usage Model –See Section 8.4.4 for details. The default value is 0b.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            # Bit 6: Usage Model (0b: Lane Margining at Receiver, 1b: Reserved)
            # If the ‘Usage Model’ field is 1b, Bits [5:0] of Symbol 4N+2 and Bits [7:0] of Symbol 4N+3 are Reserved.
            data = data | ((usage_model & 0x1) << 6)  # 6:6
            # Margin Payload –See Section 8.4.4 for details. This field value is used in conjunction with the Margin Type field as described in Section 8.4.4.
            # The default value is 0x9C.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            data = data | ((margin_payload & 0xFF) << 8)  # 15:8
            err = self.pcilib.write(address=self.CAP_LMT_OFFSET + address, data=data, width=16)
            if err == -1:
                return {"error": "ERROR: write_MarginingLaneControlRegister - write"}
            else:
                return {"error": None}

    @handle_lane_status
    def decode_MarginingLaneStatusRegister(self, lane=0):
        address = 0xA + (lane * 0x4)
        data = self.pcilib.read(address=self.CAP_LMT_OFFSET + address, width=16)
        if data == -1:
            return {"error": "ERROR: decode_MarginingLaneStatusRegister"}
        else:
            # Receiver Number Status. – See Section 8.4.4 for details. The default value is 000b.
            # For Downstream Ports, this field must be reset to the default value if the Port goes to DL_Down status.
            receiver_number_status = (data >> 0) & 0x7  # 2:0
            # Margin Type Status –See Section 8.4.4 for details. The default value is 000b.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            margin_type_status = (data >> 3) & 0x7  # 5:3
            # Usage Model Status –See Section 8.4.4 for details. The default value is 0b.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            # Bit 6: Usage Model (0b: Lane Margining at Receiver, 1b: Reserved)
            # If the ‘Usage Model’ field is 1b, Bits [5:0] of Symbol 4N+2 and Bits [7:0] of Symbol 4N+3 are Reserved.
            usage_model_status = (data >> 6) & 0x1  # 6:6
            # Margin Payload Status –See Section 8.4.4 for details. This field is only meaningful when the Margin Type is defined encoding other than ‘No Command’.
            # The default value is 0x00.
            # This field must be reset to the default value if the Port goes to DL_Down status.
            margin_payload_status = (data >> 8) & 0xFF  # 15:8
            return {
                "error": None,
                "receiver_number_status": receiver_number_status,
                "margin_type_status": margin_type_status,
                "usage_model_status": usage_model_status,
                "margin_payload_status": margin_payload_status,
            }

    # Lane Margining at Receiver, as defined in this Section, is mandatory for all Ports supporting 16.0 GT/s Data Rate,
    # including Pseudo Ports (Retimers).
    # Lane Margining at Receiver enables system software to obtain the margin information of a given Receiver while the Link is in the L0 state.
    # The margin information includes both voltage and time, in either direction from the current Receiver position.
    # For all Ports that implement Lane Margining at Receiver, Lane Margining at Receiver for timing is required,
    # while support of Lane Margining at Receiver for voltage is optional. Lane Margining at Receiver begins when a margin command is received,
    # the Link is operating at 16.0 GT/s Data Rate or higher, and the Link is in L0 state. Lane Margining at Receiver ends when
    # either a ‘Go to Normal Settings’ command is received, the Link changes speed, or the Link exits either the L0 or Recovery states.
    # Lane Margining at Receiver optionally ends when certain error thresholds are exceeded.
    # Lane Margining at Receiver is is permitted to be suspended while the Link is in Recovery for independent samplers.
    # Lane Margining at Receiver is not supported by PCIe Links operating at 2.5 GT/s, 5.0 GT/s, or 8.0 GT/s.
    @handle_lane_status
    def NoCommand(self, lane):
        # No Command is also an independent command in Upstream direction. The expected Response is No Command with the Receiver Number = 000b.
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=0x0,
            margin_type=0x7,
            usage_model=0x0,
            margin_payload=0x9C,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["receiver_number_status"] != 0x0 and ret["margin_payload_status"] != 0x9C:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: NoCommand - Timedout"}
        return {"error": None}

    @handle_lane_status
    def AccessRetimerRegister(self, lane, receiver_number, register_offset):
        # receiver_number:0x4,0x2
        # margin_payload:Registers Offset in Bytes 0x0-0x87, 0xA0-0xFF
        # margin_type:0x1
        # ResponseMarginPayload: Register value, if supported. Target Receiver on Retimer returns 00h if it does not support accessing its registers.
        if receiver_number not in (0x2, 0x4) or register_offset not in [*range(0x0, 0x88)] + [*range(0xA0, 0x100)]:
            return {
                "error": f"ERROR: AccessRetimerRegister - BAD receiver_number {receiver_number} or register_offset {register_offset}"
            }
        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=register_offset,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: AccessRetimerRegister - Timedout"}
        if ret["receiver_number_status"] == 0:
            return {"error": "ERROR: AccessRetimerRegister - receiver_number_status = 0"}
        else:
            register_value = ret["margin_payload_status"] & 0xFF
            return {"error": None, "register_value": register_value}

    @handle_lane_status
    def FetchMarginControlCapabilities(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload[7:5] = Reserved;
        # Margin Payload[4:0] = {Mind_error_sampler, Msample_reporting_method, Mind_left_right_timing, Mind_up_down_voltage, Mvoltage_supported}
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchMarginControlCapabilities - Invalid receiver_number {receiver_number}"}
        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x88,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchMarginControlCapabilities - Timedout"}

        self.device_info.lmt_capable = True
        self.device_info.ind_error_sampler = (ret["margin_payload_status"] & 0x10) >> 4
        self.device_info.sample_reporting_method = (ret["margin_payload_status"] & 0x08) >> 3
        self.device_info.ind_left_right_timing = (ret["margin_payload_status"] & 0x04) >> 2
        self.device_info.ind_up_down_voltage = (ret["margin_payload_status"] & 0x02) >> 1
        self.device_info.voltage_supported = (ret["margin_payload_status"] & 0x01) >> 0

        self.FetchNumVoltageSteps(lane=lane, receiver_number=receiver_number)
        self.FetchNumTimingSteps(lane=lane, receiver_number=receiver_number)
        self.FetchMaxTimingOffset(lane=lane, receiver_number=receiver_number)
        self.FetchMaxVoltageOffset(lane=lane, receiver_number=receiver_number)
        self.FetchSamplingRateVoltage(lane=lane, receiver_number=receiver_number)
        self.FetchSamplingRateTiming(lane=lane, receiver_number=receiver_number)
        self.FetchSampleCount(lane=lane, receiver_number=receiver_number)
        self.FetchMaxLanes(lane=lane, receiver_number=receiver_number)

        return {"error": None}

    @handle_lane_status
    def FetchNumVoltageSteps(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7] = Reserved Margin Payload[6:0] = MNumVoltageSteps
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchNumVoltageSteps - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x89,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchNumVoltageSteps - Timedout"}

        self.device_info.num_voltage_steps = (ret["margin_payload_status"] & 0x7F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchNumTimingSteps(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7:6] = Reserved Margin Payload [5:0] = MNumTimingSteps
        if receiver_number not in [*range(0x1, 0x7)]:
            return {
                "error": f"ERROR: FetchNumTimingSteps - BAD receiver_number {receiver_number}",
            }

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x8A,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchNumTimingSteps - Timedout"}

        self.device_info.num_timing_steps = (ret["margin_payload_status"] & 0x3F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchMaxTimingOffset(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7] = Reserved Margin Payload[6:0] = MMaxTimingOffset
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchMaxTimingOffset - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x8B,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchMaxTimingOffset - Timedout"}

        self.device_info.max_timing_offset = (ret["margin_payload_status"] & 0x7F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchMaxVoltageOffset(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7] = Reserved Margin Payload[6:0] = MMaxVoltageOffset
        if receiver_number not in [*range(0x1, 0x7)]:
            return {
                "error": f"ERROR: FetchMaxVoltageOffset - BAD receiver_number {receiver_number}",
            }

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x8C,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchMaxVoltageOffset - timedout"}

        self.device_info.max_voltage_offset = (ret["margin_payload_status"] & 0x7F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchSamplingRateVoltage(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7:6] = Reserved Margin Payload[5:0] = { MSamplingRateVoltage [5:0]}
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchSamplingRateVoltage - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x8D,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchSamplingRateVoltage - timedout"}

        self.device_info.sampling_rate_voltage = (ret["margin_payload_status"] & 0x3F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchSamplingRateTiming(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7:6] = Reserved Margin Payload[5:0] = { MSamplingRateTiming [5:0]}
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchSamplingRateTiming - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x8E,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchSamplingRateTiming - timedout"}

        self.device_info.sampling_rate_timing = (ret["margin_payload_status"] & 0x3F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchSampleCount(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7] = Reserved Margin Payload[6:0] = MSampleCount
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchSampleCount - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x8F,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                # MSampleCount Value = 3*log2 (number of bits margined). The count saturates at 127 (after approximately 5.54 × 1012 bits).
                return {"error": "ERROR: FetchSampleCount - timedout"}

        sample_count = (ret["margin_payload_status"] & 0x7F) >> 0
        sample_count_bits = int(pow(2, sample_count / 3))
        sample_count_bits_sci = "%.2E" % pow(2, sample_count / 3)
        return {
            "error": None,
            "sample_count": sample_count,
            "sample_count_bits": sample_count_bits,
            "sample_count_bits_sci": sample_count_bits_sci,
        }

    @handle_lane_status
    def FetchMaxLanes(self, lane, receiver_number):
        # ResponseMarginPayload: Margin Payload [7:5] = Reserved Margin Payload[4:0] = MMaxLanes
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: FetchMaxLanes - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x90,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchMaxLanes - timedout"}

        self.device_info.max_lanes = (ret["margin_payload_status"] & 0x1F) >> 0
        return {"error": None}

    @handle_lane_status
    def FetchReserved(self, lane, receiver_number, register_offset):
        # ResponseMarginPayload: register_offset Range 91-9Fh
        # Margin Payload[7:0] = Reserved
        if receiver_number not in [*range(0x1, 0x7)] or register_offset not in [*range(0x91, 0xA0)]:
            return {
                "error": f"ERROR: FetchReserved - BAD receiver_number {receiver_number} OR BAD register_offset {register_offset}"
            }

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x1,
            usage_model=0x0,
            margin_payload=0x90,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x1:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: FetchReserved - timedout"}

        self.device_info.reserved = (ret["margin_payload_status"] & 0xFF) >> 0
        return {"error": None}

    @handle_lane_status
    def SetErrorCountLimit(self, lane, receiver_number, error_count_limit):
        # ResponseMarginPayload: Margin Payload [7:6] = 11b Margin Payload[5:0] = Error Count Limit registered by the target Receiver
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: SetErrorCountLimit - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        margin_payload = 0x3 << 6 | (error_count_limit & 0x3F)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x2,
            usage_model=0x0,
            margin_payload=margin_payload,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x2:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: SetErrorCountLimit - timedout"}

        return {"error": None}

    @handle_lane_status
    def GotoNormalSettings(self, lane, receiver_number):
        # ResponseMarginPayload: 0Fh
        if receiver_number not in [*range(0x0, 0x7)]:
            return {"error": f"ERROR: GotoNormalSettings - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x2,
            usage_model=0x0,
            margin_payload=0x0F,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x2 and ret["margin_payload_status"] != 0x0F:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: GotoNormalSettings - timedout"}

        value = (ret["margin_payload_status"] & 0xFF) >> 0
        return {"error": None, "value": value}

    @handle_lane_status
    def ClearErrorLog(self, lane, receiver_number):
        # ResponseMarginPayload: 55h
        if receiver_number not in [*range(0x0, 0x7)]:
            return {"error": f"ERROR: ClearErrorLog - BAD receiver_number {receiver_number}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x2,
            usage_model=0x0,
            margin_payload=0x55,
        )
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x2 and ret["margin_payload_status"] != 0x55:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: ClearErrorLog - timedout"}

        value = (ret["margin_payload_status"] & 0xFF) >> 0
        return {"error": None, "value": value}

    @handle_lane_status
    def StepMarginTimingOffsetRightLeftOfDefault(self, lane, receiver_number, left_right_none=0, steps=6):
        # LeftRightNone
        # 0 indicates to move the Receiver to the right of the normal setting to be used when ind_left_right_timing = 1.
        # 1 indicates to move the Receiver to the left of the normal setting to be used when ind_left_right_timing = 1.
        # -1 is to indicate that Receiver does not support LeftRight to be used when ind_left_right_timing = 0
        # If ind_left_right_timing for the targeted Receiver is Set:
        #   o Margin Payload [6] indicates whether the margin command is right vs left. A 0b indicates to move the Receiver to the right of the normal setting whereas a 1b indicates to move the Receiver to the left of the normal setting.
        #   o MarginPayload[5:0]indicatesthenumberofstepstotheleftorrightofthenormal setting.
        # If ind_left_right_timing for the targeted Receiver is Clear:
        #   o Margin Payload [6]: Reserved
        #   o Margin Payload [5:0] indicates the number of steps beyond the normal setting.
        # ResponseMarginPayload: Margin Payload[7:6] =
        # 11b: NAK. Indicates that an unsupported Lane Margining command was issued. For example,timing margin beyond +/- 0.2 UI. MErrorCount is 0.
        # 10b: Margining in progress. The Receiver is executing the step margin command. MErrorCount reflects the number of errors detected as defined in Section 8.4.4
        # 01b: Set up for margin in progress. This indicates the Receiver is getting ready but has not yet started executing the step margin command. MErrorCount is 0.
        # 00b: Too many errors – Receiver autonomously went back to its default settings. MErrorCount reflects the number of errors detected as defined in Section 8.4.4. Note that MErrorCount might be greater than Error Count Limit.
        # Margin Payload[5:0] = MErrorCount
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: StepMarginTimingOffsetRightLeftOfDefault - BAD receiver_number {receiver_number}"}

        if left_right_none == -1:
            margin_payload = steps
        elif left_right_none in (0, 1):
            margin_payload = left_right_none << 6 | steps
        else:
            return {"error": f"ERROR: StepMarginTimingOffsetRightLeftOfDefault - BAD left_right_none {left_right_none}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x3,
            usage_model=0x0,
            margin_payload=margin_payload,
        )
        return self.decode_StepMarginTimingOffsetRightLeftOfDefault(lane)

    @handle_lane_status
    def decode_StepMarginTimingOffsetRightLeftOfDefault(self, lane):
        # LeftRightNone
        # 0 indicates to move the Receiver to the right of the normal setting to be used when ind_left_right_timing = 1.
        # 1 indicates to move the Receiver to the left of the normal setting to be used when ind_left_right_timing = 1.
        # -1 is to indicate that Receiver does not support LeftRight to be used when ind_left_right_timing = 0
        # If ind_left_right_timing for the targeted Receiver is Set:
        #   o Margin Payload [6] indicates whether the margin command is right vs left. A 0b indicates to move the Receiver to the right of the normal setting whereas a 1b indicates to move the Receiver to the left of the normal setting.
        #   o MarginPayload[5:0]indicatesthenumberofstepstotheleftorrightofthenormal setting.
        # If ind_left_right_timing for the targeted Receiver is Clear:
        #   o Margin Payload [6]: Reserved
        #   o Margin Payload [5:0] indicates the number of steps beyond the normal setting.
        # ResponseMarginPayload: Margin Payload[7:6] =
        # 11b: NAK. Indicates that an unsupported Lane Margining command was issued. For example,timing margin beyond +/- 0.2 UI. MErrorCount is 0.
        # 10b: Margining in progress. The Receiver is executing the step margin command. MErrorCount reflects the number of errors detected as defined in Section 8.4.4
        # 01b: Set up for margin in progress. This indicates the Receiver is getting ready but has not yet started executing the step margin command. MErrorCount is 0.
        # 00b: Too many errors – Receiver autonomously went back to its default settings. MErrorCount reflects the number of errors detected as defined in Section 8.4.4. Note that MErrorCount might be greater than Error Count Limit.
        # Margin Payload[5:0] = MErrorCount
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x3:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: decode_StepMarginTimingOffsetRightLeftOfDefault - timedout"}

        step_margin_execution_status = (ret["margin_payload_status"] & 0xC0) >> 6
        error_count = (ret["margin_payload_status"] & 0x3F) >> 0
        margin_type_status = ret["margin_type_status"]
        return {
            "error": None,
            "margin_type_status": margin_type_status,
            "step_margin_execution_status": step_margin_execution_status,
            "step_margin_execution_status_description": MARGIN_RESPONSE[step_margin_execution_status],
            "error_count": error_count,
        }

    @handle_lane_status
    def StepMarginVoltageOffsetUpDownOfDefault(self, lane, receiver_number, up_down=0, steps=32):
        # UpDown
        # 0 indicates to move the Receiver to the Up from Normal.
        # 1 indicates to move the Receiver to the Down from Normal.
        # If Mind_up_down_voltage for the targeted Receiver is Set:
        #  o Margin Payload [7] indicates whether the margin command is up vs down. A 0b indicates to move the Receiver up from the normal setting whereas a 1b indicates to move the Receiver down from the normal setting.
        #  o Margin Payload [6:0] indicates the number of steps up or down from the normal setting.
        # If Mind_up_down_voltage for the targeted Receiver is Clear:
        #  o Margin Payload [7]: Reserved
        #  o Margin Payload [6:0] indicates the number of steps beyond the normal setting.
        # ResponseMarginPayload: Margin Payload[7:6] =
        # 11b: NAK. Indicates that an unsupported Lane Margining command was issued. For example,timing margin beyond +/- 0.2 UI. MErrorCount is 0.
        # 10b: Margining in progress. The Receiver is executing the step margin command. MErrorCount reflects the number of errors detected as defined in Section 8.4.4
        # 01b: Set up for margin in progress. This indicates the Receiver is getting ready but has not yet started executing the step margin command. MErrorCount is 0.
        # 00b: Too many errors – Receiver autonomously went back to its default settings. MErrorCount reflects the number of errors detected as defined in Section 8.4.4. Note that MErrorCount might be greater than Error Count Limit.
        # Margin Payload[5:0] = MErrorCount
        if receiver_number not in [*range(0x1, 0x7)]:
            return {"error": f"ERROR: StepMarginVoltageOffsetUpDownOfDefault - BAD receiver_number {receiver_number}"}

        if steps not in [
            *range(
                PARAMETERS["NumVoltageSteps"]["min"],
                PARAMETERS["NumVoltageSteps"]["max"] + 1,
            )
        ]:
            return {"error": f"ERROR: StepMarginVoltageOffsetUpDownOfDefault - BAD Steps {steps}"}

        if up_down in (0, 1):
            margin_payload = up_down << 6 | steps
        else:
            return {"error": f"ERROR: StepMarginVoltageOffsetUpDownOfDefault - BAD UpDown {up_down}"}

        self.NoCommand(lane=lane)
        self.write_MarginingLaneControlRegister(
            lane=lane,
            receiver_number=receiver_number,
            margin_type=0x4,
            usage_model=0x0,
            margin_payload=margin_payload,
        )
        return self.decode_StepMarginVoltageOffsetUpDownOfDefault(lane)

    @handle_lane_status
    def decode_StepMarginVoltageOffsetUpDownOfDefault(self, lane):
        # UpDown
        # 0 indicates to move the Receiver to the right of the normal setting to be used when ind_left_right_timing = 1.
        # 1 indicates to move the Receiver to the left of the normal setting to be used when ind_left_right_timing = 1.
        # If Mind_up_down_voltage for the targeted Receiver is Set:
        #  o Margin Payload [7] indicates whether the margin command is up vs down. A 0b indicates to move the Receiver up from the normal setting whereas a 1b indicates to move the Receiver down from the normal setting.
        #  o Margin Payload [6:0] indicates the number of steps up or down from the normal setting.
        # If Mind_up_down_voltage for the targeted Receiver is Clear:
        #  o Margin Payload [7]: Reserved
        #  o Margin Payload [6:0] indicates the number of steps beyond the normal setting.
        # ResponseMarginPayload: Margin Payload[7:6] =
        # 11b: NAK. Indicates that an unsupported Lane Margining command was issued. For example,timing margin beyond +/- 0.2 UI. MErrorCount is 0.
        # 10b: Margining in progress. The Receiver is executing the step margin command. MErrorCount reflects the number of errors detected as defined in Section 8.4.4
        # 01b: Set up for margin in progress. This indicates the Receiver is getting ready but has not yet started executing the step margin command. MErrorCount is 0.
        # 00b: Too many errors – Receiver autonomously went back to its default settings. MErrorCount reflects the number of errors detected as defined in Section 8.4.4. Note that MErrorCount might be greater than Error Count Limit.
        # Margin Payload[5:0] = MErrorCount
        ret = self.decode_MarginingLaneStatusRegister(lane=lane)
        start_time = time.time()
        while ret["margin_type_status"] != 0x4:
            ret = self.decode_MarginingLaneStatusRegister(lane=lane)
            if time.time() - start_time > TIMEOUT:
                return {"error": "ERROR: decode_StepMarginVoltageOffsetUpDownOfDefault - timedout"}

        step_margin_execution_status = (ret["margin_payload_status"] & 0xC0) >> 6
        error_count = (ret["margin_payload_status"] & 0x3F) >> 0
        margin_type_status = ret["margin_type_status"]
        return {
            "error": None,
            "margin_type_status": margin_type_status,
            "step_margin_execution_status": step_margin_execution_status,
            "step_margin_execution_statusDescription": MARGIN_RESPONSE[step_margin_execution_status],
            "error_count": error_count,
        }
