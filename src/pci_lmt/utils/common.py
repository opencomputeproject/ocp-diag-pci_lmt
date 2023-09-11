import dataclasses
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple


# Increment MAJOR version when you make incompatible API changes
# Increment MINOR version when you add functionality in a backward compatible manner
# Increment PATCH version when you make backward compatible bug fixes
VERSION = "1.1.1"


@dataclass
class LmtTestInfo:
    """Class to hold test level info for the LMT test."""

    run_id: str = ""
    timestamp: int = -1
    asset_id: int = -1
    hostname: str = ""
    model_name: str = ""
    dwell_time_secs: int = -1
    elapsed_time_secs: float = -1
    error_count_limit: int = -1
    test_version: str = ""
    annotation: str = ""


@dataclass
class LmtDeviceInfo:
    """Class to hold device level info for the LMT test."""

    bdf: str = ""
    speed: str = ""
    width: str = ""
    lmt_capable: bool = False
    ind_error_sampler: bool = False
    sample_reporting_method: int = 0
    ind_left_right_timing: bool = False
    ind_up_down_voltage: bool = False
    voltage_supported: bool = False
    num_voltage_steps: int = 0
    num_timing_steps: int = 0
    max_timing_offset: int = 0
    max_voltage_offset: int = 0
    sampling_rate_voltage: int = 0
    sampling_rate_timing: int = 0
    max_lanes: int = 0
    reserved: int = 0


@dataclass
class LmtLaneResult:
    """Class to hold lane level info for the LMT test."""

    test_info: LmtTestInfo = LmtTestInfo()
    device_info: LmtDeviceInfo = LmtDeviceInfo()
    lane: int = -1
    receiver_number: int = -1
    margin_type: str = ""
    step: int = -1
    sample_count: int = -1
    sample_count_bits: int = -1
    error_count: int = -1
    ber: float = -1.0
    error: bool = True
    error_msg: str = ""

    def to_json(self) -> str:
        """Converts the object into a JSON string."""
        return json.dumps(dataclasses.asdict(self))

    def to_csv(self) -> Tuple[str, str]:
        """Converts the object into a CSV string and returns header and row."""
        nested_dict = dataclasses.asdict(self)
        flat_dict = {}
        for key, value in nested_dict.items():
            if isinstance(value, dict):
                for inner_key, val in value.items():
                    flat_dict[f"{key}.{inner_key}"] = val
            else:
                flat_dict[key] = value

        header = ",".join(flat_dict.keys())
        row = ",".join(str(value) for value in flat_dict.values())
        return header, row


def add_common_args(parser) -> None:
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
        "-o",
        dest="output",
        type=str,
        help="Output format. Supported formats: scribe, json. Default: json",
        default="json",
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
        version="%(prog)s " + VERSION,
    )


def get_platform_config_local(config_file: str) -> Dict[str, Any]:
    """Returns the LMT configuration as a dict from the given configuration file."""
    with open(config_file, "r") as f:
        return json.loads(f.read())


def get_margin_directions(cfg: Dict[str, Any]) -> Tuple[int, int]:
    """Returns the margin direction as a tuple."""
    left_right_none = -1
    up_down = -1
    margin_info = (cfg["margin_type"], cfg["margin_direction"])
    if margin_info == ("TIMING", "right"):
        left_right_none = 0
    elif margin_info == ("TIMING", "left"):
        left_right_none = 1
    elif margin_info == ("VOLTAGE", "up"):
        up_down = 0
    elif margin_info == ("VOLTAGE", "down"):
        up_down = 1
    else:
        raise ValueError(
            f"Invalid values for margin_type {cfg['margin_type']} and/or "
            f"margin_direction {cfg['margin_direction']}."
        )

    return (left_right_none, up_down)


def get_run_id() -> str:
    """Returns an unique ID using RNG."""
    return (
        os.popen("od -N 16 -t uL -An /dev/urandom | sed 's/ //g'").read().split("\n")[0]
    )


def get_curr_timestamp() -> int:
    """Returns the current unix timestamp."""
    return int(os.popen("date +%s").read().split("\n")[0])
