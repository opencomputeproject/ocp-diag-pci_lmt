import socket

from .common import LmtLaneResult


def send_to_db(result: LmtLaneResult) -> None:
    pass


def get_host_name() -> str:
    return socket.gethostname()


def get_asset_id() -> str:
    return ""


def get_model_name() -> str:
    return ""
