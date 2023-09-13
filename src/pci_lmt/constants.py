# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import dataclasses as dc
import typing as ty

# FIXME: this looks like an enum
EXPRESS_TYPES: ty.Dict[int, str] = {
    0x0: "endpoint",
    0x1: "legacy_endpoint",
    0x4: "root_port",
    0x5: "upstream_port",
    0x6: "downstream_port",
    0x7: "pci_bridge",
    0x8: "pcie_bridge",
    0x9: "root_complex_endpoint",
    0xA: "root_complex_event_collector",
}

# FIXME: this looks like an enum
EXPRESS_SPEED: ty.Dict[int, str] = {
    1: "2.5GT/s",
    2: "5GT/s",
    3: "8GT/s",
    4: "16GT/s",
    5: "32GT/s",
    6: "64GT/s",
}

# ResponseMarginPayload: Margin Payload[7:6] =
# 11b: NAK. Indicates that an unsupported Lane Margining command was issued. For example,timing margin beyond
# +/- 0.2 UI. MErrorCount is 0.
# 10b: Margining in progress. The Receiver is executing the step margin command. MErrorCount reflects the number of
# errors detected as defined in Section 8.4.4
# 01b: Set up for margin in progress. This indicates the Receiver is getting ready but has not yet started executing
# the step margin command. MErrorCount is 0.
# 00b: Too many errors – Receiver autonomously went back to its default settings. MErrorCount reflects the number of
# errors detected as defined in Section 8.4.4. Note that MErrorCount might be greater than Error Count Limit.
# Margin Payload[5:0] = MErrorCount

# FIXME: this looks like an enum
MARGIN_RESPONSE: ty.Dict[int, str] = {
    0: "Too Many Errors",
    1: "Setup for Margin In Progress",
    2: "Margining Started and In Process",
    3: "Command Not Supported",
}


@dc.dataclass
class Parameter:  # pylint: disable=too-few-public-methods
    min: int
    max: int
    description: str


PARAMETERS: ty.Dict[str, Parameter] = {
    "NumTimingSteps": Parameter(
        min=6,
        max=63,
        description=(
            "Number of time steps from default (to either left or right), range must be at least +/-0.2 UI Timing"
            " offset must increase monotonically The number of steps in both positive (toward the end of the unit"
            " interval) and negative (toward the beginning of the unit interval) must be identical"
        ),
    ),
    "MaxTimingOffset": Parameter(
        min=20,
        max=50,
        description=(
            "Offset from default at maximum step value as percentage of a nominal UI at 16.0 GT/s A 0 value may be"
            " reported if the vendor chooses not to report the offset"
        ),
    ),
    "NumVoltageSteps": Parameter(
        min=32,
        max=127,
        description=(
            "Number of voltage steps from default (either up or down), minimum range +/-50 mV as measured by 16.0 GT/s"
            " reference equalizer Voltage offset must increase monotonically The number of steps in both positive and"
            " negative direction from the default sample location must be identical This value is undefined if"
            " MVoltageSupported is 0b"
        ),
    ),
    "MaxVoltageOffset": Parameter(
        min=5,
        max=50,
        description=(
            "Offset from default at maximum step value as percentage of one volt A 0 value may be reported if the"
            " vendor chooses not to report the offset when MVoltageSupported is 1b This value is undefined if"
            " MVoltageSupported is 0b"
        ),
    ),
    "SamplingRateVoltage": Parameter(
        min=0,
        max=63,
        description=(
            "The ratio of bits tested to bits received during voltage margining. A value of 0 is a ratio of 1:64 (1 bit"
            " of every 64 bits received), and a value of 63 is a ratio of 64:64 (all bits received)."
        ),
    ),
    "SamplingRateTiming": Parameter(
        min=0,
        max=63,
        description=(
            "The ratio of bits tested to bits received during timing margining. A value of 0 is a ratio of 1:64 (1 bit"
            " of every 64 bits received), and a value of 63 is a ratio of 64:64 (all bits received)."
        ),
    ),
    "VoltageSupported": Parameter(
        min=0,
        max=1,
        description="1b indicates that voltage margining is supported",
    ),
    "IndLeftRightTiming": Parameter(
        min=0,
        max=1,
        description="1b indicates independent left/right timing margin supported",
    ),
    "IndUpDownVoltage": Parameter(
        min=0,
        max=1,
        description="1b independent up and down voltage margining supported",
    ),
    "IndErrorSampler": Parameter(
        min=0,
        max=1,
        description=(
            "1b Margining will not produce errors (change in the error rate) in data stream (ie. – error sampler is"
            " independent) 0b Margining may produce errors in the data stream"
        ),
    ),
    "MaxLanes": Parameter(
        min=0,
        max=31,
        description=(
            "Maximum number of Lanes minus 1 that can be margined at the same time. It is recommended that this value"
            " be greater than or equal to the number of Lanes in the Link minus 1. Encoding Behavior is undefined if"
            " software attempts to margin more than MMaxLanes+1 at the same time. Note: This value is permitted to"
            " exceed the number of Lanes in the Link minus 1."
        ),
    ),
    "SampleReportingMethod": Parameter(
        min=0,
        max=1,
        description=(
            "Indicates whether sampling rates (MSamplingRateVoltage and MSamplingRateTiming) are supported (1) or a"
            " sample count is supported (0). One of the two methods is supported by each device."
        ),
    ),
    "ErrorCount": Parameter(
        min=0,
        max=63,
        description=(
            "If MIndErrorSampler is 1b this is a count of the actual bit errors since margining started. If"
            " MIndErrorSampler is 0b this is the actual count of the logical errors since margining started. See the"
            " Physical Layer Logical Block chapter for the definition of what errors are counted. The count saturates"
            " at 63."
        ),
    ),
    "SampleCount": Parameter(
        min=0,
        max=127,
        description=(
            "Value = 3*log2 (number of bits margined). Where number of bits margined is a count of the actual number of"
            " bits tested during marging. The count stops when margining stops. The count saturates at 127 (after"
            " approximately 5.54 × 1012 bits). The count resets to zero when a new margin command is received."
        ),
    ),
}
