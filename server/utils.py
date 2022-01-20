from bitcoinutils.keys import P2pkhAddress
from bitcoinutils.setup import setup
from bitcoinutils import constants
from datetime import timedelta
import requests
import config
import math
import json

def datetime_round_day(timestamp):
    return timestamp - timedelta(
        days=timestamp.day % 1,
        hours=timestamp.hour,
        minutes=timestamp.minute,
        seconds=timestamp.second,
        microseconds=timestamp.microsecond
    )

def hash160_to_address(hash160):
    constants.NETWORK_SEGWIT_PREFIXES["mainnet"] = "eqpay"
    constants.NETWORK_P2PKH_PREFIXES["mainnet"] = b"\x21"
    constants.NETWORK_P2SH_PREFIXES["mainnet"] = b"\x3A"
    constants.NETWORK_WIF_PREFIXES["mainnet"] = b"\x46"

    setup("mainnet")

    address = P2pkhAddress.from_hash160(hash160)

    return address.to_string()

def dead_response(message="Invalid Request", rid=config.rid):
    return {"error": {"code": 404, "message": message}, "id": rid}

def response(result, error=None, rid=config.rid):
    return {"error": error, "id": rid, "result": result}

def make_request(method, params=[]):
    headers = {"content-type": "text/plain;"}
    data = json.dumps({"id": config.rid, "method": method, "params": params})

    try:
        return requests.post(config.endpoint, headers=headers, data=data).json()
    except Exception:
        return dead_response()

def reward(height):
    halvings = height // 525960

    if halvings >= 10:
        return 0

    return int(satoshis(4) // (2 ** halvings))

def supply(height):
    premine = satoshis(9000000)
    reward = satoshis(2)
    halvings = 525960
    halvings_count = 0
    supply = reward

    while height > halvings:
        total = halvings * reward
        reward -= satoshis(0.13) * halvings_count
        height = height - halvings
        halvings_count += 1

        supply += total

    supply = supply + height * reward

    if height > 1:
        supply += premine

    return {
        "halvings": int(halvings_count),
        "supply": int(supply)
    }

def satoshis(value):
    return int(float(value) * math.pow(10, 8))

def amount(value, decimals=8):
    return round(float(value) / math.pow(10, decimals), decimals)

def pagination(url, page, items, total):
    pagination = range(page - 4, page + 5)
    pagination = [item for item in pagination if item >= 1 and item <= total]
    previous_page = page - 1 if page != 1 else None
    next_page = page + 1 if page != total else None

    return {
        "total": total,
        "current": page,
        "pages": pagination,
        "previous": previous_page,
        "next": next_page,
        "url": url
    }
