# (c) Meta Platforms, Inc. and affiliates.
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

import dataclasses as dc
import json
import textwrap
import typing as ty


@dc.dataclass
class ConfigLmtGroup:
    name: str
    receiver_number: int
    bdf_list: ty.List[str]
    margin_type: ty.Union[ty.Literal["VOLTAGE"], ty.Literal["TIMING"]]
    margin_direction: ty.Union[
        ty.Literal["right"],
        ty.Literal["left"],
        ty.Literal["up"],
        ty.Literal["down"],
    ]
    margin_steps: ty.List[int]

    # NOTE: this may need to be refactored to return some enum types; a tuple of ints
    # is not really descriptive
    @property
    def margin_directions_tuple(self) -> ty.Tuple[int, int]:
        """Returns the margin direction as a tuple."""
        left_right_none = -1
        up_down = -1
        margin_info = (self.margin_type, self.margin_direction)
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
                f"Invalid values for margin_type {self.margin_type} and/or margin_direction {self.margin_direction}."
            )

        return (left_right_none, up_down)

    def __str__(self) -> str:
        bdf = textwrap.indent("\n".join(self.bdf_list), " " * 16).lstrip()
        return textwrap.dedent(
            f"""
            {self.name}
            receiver_number: {self.receiver_number}
            bdf:
                {bdf}
            type: {self.margin_type}
            direction: {self.margin_direction}
            steps: {self.margin_steps}
        """
        )

    @staticmethod
    def from_json(data: ty.Dict[str, ty.Any]) -> "ConfigLmtGroup":
        return ConfigLmtGroup(
            name=data["name"],
            receiver_number=data["receiver_number"],
            bdf_list=data["bdf_list"],
            margin_type=data["margin_type"],
            margin_direction=data["margin_direction"],
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
