# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import dataclasses as dc
import json
import textwrap
import typing as ty

from enum import Enum


class MarginType(str, Enum):
    VOLTAGE_NONE = "voltage_none"
    VOLTAGE_UP = "voltage_up"
    VOLTAGE_DOWN = "voltage_down"
    TIMING_NONE = "timing_none"
    TIMING_RIGHT = "timing_right"
    TIMING_LEFT = "timing_left"


@dc.dataclass
class ConfigLmtGroup:
    name: str
    receiver_number: int
    bdf_list: ty.List[str]
    margin_type: MarginType
    margin_steps: ty.List[int]

    def __str__(self) -> str:
        bdf = textwrap.indent("\n".join(self.bdf_list), " " * 16).lstrip()
        return textwrap.dedent(
            f"""
            {self.name}
            receiver_number: {self.receiver_number}
            bdf:
                {bdf}
            type: {self.margin_type}
            steps: {self.margin_steps}
        """
        )

    @staticmethod
    def from_json(data: ty.Dict[str, ty.Any]) -> "ConfigLmtGroup":
        try:
            input_margin_type = data["margin_type"].lower()
            input_margin_direction = data["margin_direction"].lower()
            margin_type = MarginType(f"{input_margin_type}_{input_margin_direction}")
        except ValueError as e:
            raise ValueError(
                f"Invalid margin type: {input_margin_type} and/or direction: {input_margin_direction}. "
                f"Valid values are: {MarginType.__members__}"
            ) from e

        return ConfigLmtGroup(
            name=data["name"],
            receiver_number=data["receiver_number"],
            bdf_list=data["bdf_list"],
            margin_type=margin_type,
            margin_steps=data["margin_steps"],
        )


@dc.dataclass
class PlatformConfig:
    platform_name: str
    lmt_groups: ty.List[ConfigLmtGroup]

    def __str__(self) -> str:
        groups = textwrap.indent("".join(str(g) for g in self.lmt_groups), " " * 16).lstrip()
        return textwrap.dedent(
            f"""
            platform: {self.platform_name}
            groups:
                {groups}
        """
        )

    @staticmethod
    def from_json(data: ty.Dict[str, ty.Any]) -> "PlatformConfig":
        return PlatformConfig(
            platform_name=data["platform_name"],
            lmt_groups=[ConfigLmtGroup.from_json(group) for group in data["lmt_groups"]],
        )


def read_platform_config(config_file: str) -> PlatformConfig:
    """Returns the LMT configuration as a dict from the given configuration file."""
    with open(config_file, "r", encoding="utf8") as fd:
        return PlatformConfig.from_json(json.loads(fd.read()))
