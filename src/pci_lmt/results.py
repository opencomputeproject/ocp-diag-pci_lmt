# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import dataclasses as dc
import json
import typing as ty
from contextlib import contextmanager

import ocptv.output as tv
from ocptv.output import TestResult, TestRunError, TestStatus, TestStepError
from pci_lmt import __version__ as PCI_LMT_VERSION
from pci_lmt.host import HostInfo
from pci_lmt.pcie_lane_margining import LmtDeviceInfo


@dc.dataclass
class LmtTestInfo:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Class to hold test level info for the LMT test."""

    run_id: str = ""
    timestamp: int = -1
    host_id: int = -1
    hostname: str = ""
    model_name: str = ""
    dwell_time_secs: int = -1
    elapsed_time_secs: float = -1
    error_count_limit: int = -1
    test_version: str = ""
    annotation: str = ""


@dc.dataclass
class LmtLaneResult:  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Class to hold lane level info for the LMT test."""

    test_info: LmtTestInfo = dc.field(default_factory=LmtTestInfo)
    device_info: LmtDeviceInfo = dc.field(default_factory=LmtDeviceInfo)
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
        return json.dumps(dc.asdict(self))

    def to_csv(self) -> ty.Tuple[str, str]:
        """Converts the object into a CSV string and returns header and row."""
        nested_dict = dc.asdict(self)
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


class Reporter:
    def __init__(self):
        pass

    @contextmanager
    def start_run(self, host: HostInfo):
        # pylint: disable=unused-argument
        yield

    @contextmanager
    def start_step(self, name: str):
        # pylint: disable=unused-argument
        yield

    def write(self, _result: LmtLaneResult) -> None:
        pass


class JsonStdoutReporter(Reporter):
    def write(self, result: LmtLaneResult) -> None:
        print(result.to_json())


class CsvStdoutReporter(Reporter):
    def __init__(self):
        self.__emitted_header = False

    def write(self, result: LmtLaneResult) -> None:
        header, row = result.to_csv()
        if not self.__emitted_header:
            print(header)
            self.__emitted_header = True

        print(row)


class OcptvReporter(Reporter):
    def __init__(self):
        self._run = tv.TestRun(name="pci_lmt", version=PCI_LMT_VERSION)
        self._step = None

    @contextmanager
    def start_run(self, host: HostInfo):
        # TODO(sksekar): Add support for HardwareInfo using PlatformConfig.
        dut = tv.Dut(id=host.host_id, name=host.hostname)
        try:
            yield self._run.start(dut=dut)
        except TestRunError as e:
            self._run.end(status=e.status, result=e.result)
        else:
            self._run.end(status=TestStatus.COMPLETE, result=TestResult.PASS)

    @contextmanager
    def start_step(self, name: str):
        if self._step:
            raise RuntimeError("Cannot start a new step before ending the previous one.")

        # TODO(sksekar): Add support for validators.
        self._step = self._run.add_step(name=name)
        try:
            yield self._step.start()
        except TestStepError as e:
            self._step.end(status=e.status)
        else:
            self._step.end(status=TestStatus.COMPLETE)
        finally:
            self._step = None

    def write(self, result: LmtLaneResult) -> None:
        if not self._step:
            raise RuntimeError("Cannot write results before starting a step.")

        meas_name = f"BDF:{result.device_info.bdf} Lane:{result.lane}"
        self._step.add_measurement(name=meas_name, value=result.ber)
