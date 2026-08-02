"""Small protobuf codec for the EcoFlow cloud envelope.

EcoFlow's MQTT payloads use protobuf, but the messages are not distributed as
stable public .proto files. This codec intentionally implements the wire
format needed by the adapter and keeps the device mappings data-driven.
"""
from __future__ import annotations

import struct
import time


def _varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift > 70:
            raise ValueError("invalid protobuf varint")
    raise ValueError("truncated protobuf varint")


def _fields(data: bytes) -> list[tuple[int, int, object]]:
    result = []
    offset = 0
    while offset < len(data):
        tag, offset = _varint(data, offset)
        number, wire_type = tag >> 3, tag & 7
        if wire_type == 0:
            value, offset = _varint(data, offset)
        elif wire_type == 1:
            value, offset = data[offset : offset + 8], offset + 8
        elif wire_type == 2:
            length, offset = _varint(data, offset)
            value, offset = data[offset : offset + length], offset + length
        elif wire_type == 5:
            value, offset = data[offset : offset + 4], offset + 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire_type}")
        result.append((number, wire_type, value))
    return result


def _signed(value: int, bits: int = 32) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


HEADER_FIELDS = {
    1: "pdata", 2: "src", 3: "dest", 4: "d_src", 5: "d_dest",
    6: "enc_type", 7: "check_type", 8: "cmd_func", 9: "cmd_id",
    10: "data_len", 11: "need_ack", 12: "is_ack", 14: "seq",
    15: "product_id", 16: "version", 17: "payload_ver", 18: "time_snap",
    19: "is_rw_cmd", 20: "is_queue", 21: "ack_type", 22: "code",
    23: "from", 24: "module_sn", 25: "device_sn",
}


def decode_envelope(data: bytes) -> list[dict]:
    """Decode EcoFlow HeaderMessage into header dictionaries."""
    headers = []
    for number, wire_type, value in _fields(data):
        if number != 1 or wire_type != 2:
            continue
        header = {}
        for field, field_wire, field_value in _fields(value):
            key = HEADER_FIELDS.get(field)
            if not key:
                continue
            if field_wire == 0:
                header[key] = _signed(field_value)
            elif field_wire == 2:
                header[key] = field_value if key == "pdata" else field_value.decode(errors="replace")
            else:
                header[key] = field_value
        headers.append(header)
    return headers


# cmdFunc 20 is the shared inverter/powerstream protocol used by PowerStream
# and its 600/800 W variants in the reference adapter.
PSTREAM_MESSAGES = {
    (20, 1): "inverter_heartbeat", (20, 129): "permanent_watts_pack",
    (20, 130): "supply_priority_pack", (20, 132): "bat_lower_pack",
    (20, 133): "bat_upper_pack", (20, 135): "brightness_pack",
    (20, 143): "feed_priority_pack", (20, 146): "rated_power_pack",
}

PSTREAM_FIELDS = {
    "inverter_heartbeat": {
        16: ("pv1InputVolt", 0.1), 17: ("pv1OpVolt", 0.01), 18: ("pv1InputCur", 0.1),
        19: ("pv1InputWatts", 0.1), 20: ("pv1Temp", 0.1), 21: ("pv2InputVolt", 0.1),
        22: ("pv2OpVolt", 0.01), 23: ("pv2InputCur", 0.1), 24: ("pv2InputWatts", 0.1),
        25: ("pv2Temp", 0.1), 26: ("batInputVolt", 0.1), 27: ("batOpVolt", 0.1),
        28: ("batInputCur", 0.001), 29: ("batInputWatts", 0.1), 30: ("batTemp", 0.1),
        31: ("batSoc", 1), 32: ("llcInputVolt", 0.1), 33: ("llcOpVolt", 0.01),
        34: ("llcTemp", 0.1), 35: ("invInputVolt", 0.01), 36: ("invOpVolt", 0.01),
        37: ("invOutputCur", 0.1), 38: ("invOutputWatts", 0.1), 39: ("invTemp", 0.1),
        40: ("invFreq", 0.1), 41: ("invDcCur", 0.1), 48: ("permanentWatts", 0.1),
        50: ("supplyPriority", 1), 51: ("lowerLimit", 1), 52: ("upperLimit", 1),
        53: ("invOnOff", 1), 56: ("invBrightness", 0.1), 58: ("ratedPower", 1),
        59: ("batChargingTime", 1), 60: ("batDischargingTime", 1), 61: ("feedPriority", 1),
        62: ("pv_to_inv_watts", 0.1), 63: ("grid_cons_watts", 0.1), 64: ("plug_total_watts", 0.1),
        65: ("inv_to_plug_watts", 0.1), 83: ("wifi_rssi", 1),
    },
    "rated_power_pack": {1: ("ratedPower", 1)},
    "permanent_watts_pack": {1: ("permanentWatts", 0.1)},
    "supply_priority_pack": {1: ("supplyPriority", 1)},
    "bat_lower_pack": {1: ("lowerLimit", 1)},
    "bat_upper_pack": {1: ("upperLimit", 1)},
    "brightness_pack": {1: ("invBrightness", 0.1)},
    "feed_priority_pack": {1: ("feedPriority", 1)},
}


def decode_pstream(data: bytes) -> dict[str, object]:
    values = {}
    for header in decode_envelope(data):
        message = PSTREAM_MESSAGES.get((header.get("cmd_func"), header.get("cmd_id")))
        if not message or not header.get("pdata"):
            continue
        for field, wire_type, raw in _fields(header["pdata"]):
            mapping = PSTREAM_FIELDS.get(message, {}).get(field)
            if not mapping or wire_type not in (0, 5):
                continue
            if wire_type == 5:
                raw_value = struct.unpack("<f", raw)[0]
            else:
                raw_value = _signed(raw)
            name, multiplier = mapping
            values[name] = round(raw_value * multiplier, 3)
    return values


STREAM_MESSAGES = {
    (32, 2): "CMSHeartBeatReport", (32, 50): "BMSHeartBeatReport",
    (254, 21): "DisplayPropertyUpload", (254, 22): "RuntimePropertyUpload",
}

STREAM_FIELDS = {
    "BMSHeartBeatReport": {
        6: ("bmsSoc", 1), 7: ("bmsVoltage", 0.001), 8: ("bmsCurrent", 0.001),
        9: ("bmsTemperature", 1), 14: ("bmsCycles", 1), 25: ("bmsBattSoc", 1),
        26: ("bmsInputWatts", 1), 27: ("bmsOutputWatts", 1), 28: ("bmsRemainTime", 1),
    },
    "DisplayPropertyUpload": {
        70: ("powGetPv2", 1), 242: ("bmsBattSoc", 1), 243: ("bmsBattSoh", 1),
        254: ("bmsDsgRemTime", 1), 255: ("bmsChgRemTime", 1), 258: ("bmsMinCellTemp", 1),
        259: ("bmsMaxCellTemp", 1), 260: ("bmsMinMosTemp", 1), 261: ("bmsMaxMosTemp", 1),
        262: ("cmsBattSoc", 1), 263: ("cmsBattSoh", 1), 268: ("cmsDsgRemTime", 1),
        269: ("cmsChgRemTime", 1), 270: ("cmsMaxChgSoc", 1), 271: ("cmsMinDsgSoc", 1),
        361: ("powGetPv", 1), 380: ("plugInInfoPvVol", 1), 381: ("plugInInfoPvAmp", 1),
        442: ("plugInInfoPv2Vol", 1), 461: ("backupReverseSoc", 1), 515: ("powGetSysGrid", 1),
        516: ("powGetSysLoad", 1), 517: ("powGetPvSum", 1), 518: ("powGetBpCms", 1),
        520: ("feedGridMode", 1), 521: ("feedGridModePowLimit", 1), 602: ("moduleWifiRssi", 1), 613: ("gridConnectionVol", 1),
        614: ("gridConnectionAmp", 1), 615: ("gridConnectionFreq", 1), 616: ("gridConnectionPower", 1),
        760: ("powConsumptionMeasurement", 1), 980: ("relay2Onoff", 1), 981: ("relay4Onoff", 1),
        982: ("relay3Onoff", 1), 983: ("relay1Onoff", 1), 992: ("sysGridConnectionPower", 1),
        993: ("socketMeasurePower", 1), 978: ("_dayResidentLoadList", 1), 996: ("powGetPv3", 1), 997: ("powGetPv4", 1),
    },
    "RuntimePropertyUpload": {},
}

CMS_FIELDS = {
    7: ("maxChargeSoc", 1), 9: ("lcdShowSoc", 1), 12: ("chgRemainTime", 1),
    13: ("dsgRemainTime", 1), 15: ("lcdShowSoc", 1), 21: ("minDsgSoc", 1),
    23: ("maxCloseOilEbSoc", 1),
}


def _decode_payload(data: bytes, mapping: dict[int, tuple[str, float]]) -> dict[str, object]:
    values = {}
    for field, wire_type, raw in _fields(data):
        item = mapping.get(field)
        if not item or wire_type not in (0, 5):
            continue
        raw_value = struct.unpack("<f", raw)[0] if wire_type == 5 else _signed(raw)
        name, multiplier = item
        values[name] = round(raw_value * multiplier, 3)
    return values


def decode_stream(data: bytes) -> dict[str, object]:
    values = {}
    for header in decode_envelope(data):
        message = STREAM_MESSAGES.get((header.get("cmd_func"), header.get("cmd_id")))
        if not message or not header.get("pdata"):
            continue
        if message == "CMSHeartBeatReport":
            for field, wire_type, raw in _fields(header["pdata"]):
                if field in (1, 2) and wire_type == 2:
                    values.update(_decode_payload(raw, CMS_FIELDS))
        else:
            for field, wire_type, raw in _fields(header["pdata"]):
                if field == 978 and wire_type == 2:
                    for list_field, list_wire_type, list_raw in _fields(raw):
                        if list_field != 1 or list_wire_type != 2:
                            continue
                        for nested_field, nested_wire_type, nested_raw in _fields(list_raw):
                            name = {1: "startMin1", 2: "endMin1", 3: "loadPower1"}.get(nested_field)
                            if name and nested_wire_type == 0:
                                values[name] = _signed(nested_raw)
                    continue
                mapping = STREAM_FIELDS[message].get(field)
                if not mapping or wire_type not in (0, 5):
                    continue
                raw_value = struct.unpack("<f", raw)[0] if wire_type == 5 else _signed(raw)
                name, multiplier = mapping
                if not name.startswith("_"):
                    values[name] = round(raw_value * multiplier, 3)
    return values


def _encode_varint(value: int) -> bytes:
    if value < 0:
        value &= (1 << 64) - 1
    output = bytearray()
    while value > 0x7F:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _field(number: int, wire_type: int, value: bytes | int) -> bytes:
    if wire_type == 0:
        payload = _encode_varint(value)
    elif wire_type in (1, 5):
        payload = value
    else:
        payload = _encode_varint(len(value)) + value
    return _encode_varint((number << 3) | wire_type) + payload


def encode_pstream_command(serial: str, key: str, value) -> bytes:
    commands = {
        "permanentWatts": (129, int(float(value) * 10), 3),
        "ratedPower": (146, int(value), 3), "invBrightness": (135, int(float(value) * 10), 3),
        "lowerLimit": (132, int(value), 2), "upperLimit": (133, int(value), 2),
        "supplyPriority": (130, int(bool(value)), 2), "feedPriority": (143, int(bool(value)), 2),
    }
    if key not in commands:
        raise ValueError(f"unsupported PowerStream command: {key}")
    cmd_id, cmd_value, data_len = commands[key]
    pdata = _field(1, 0, cmd_value)
    header = b"".join((
        _field(2, 0, 32), _field(3, 0, 53), _field(4, 0, 1), _field(5, 0, 1),
        _field(7, 0, 3), _field(8, 0, 20), _field(9, 0, cmd_id), _field(10, 0, data_len),
        _field(11, 0, 1), _field(14, 0, int(time.time() * 1000)), _field(16, 0, 19),
        _field(17, 0, 1), _field(23, 2, b"ios"), _field(25, 2, serial.encode()), _field(1, 2, pdata),
    ))
    return _field(1, 2, header)


def encode_pstream_get(serial: str) -> bytes:
    """Request the current PowerStream heartbeat/quotas."""
    header = b"".join((
        _field(2, 0, 32), _field(3, 0, 32), _field(14, 0, int(time.time() * 1000)),
        _field(23, 2, b"ios"), _field(25, 2, serial.encode()), _field(8, 0, 20), _field(9, 0, 1),
    ))
    return _field(1, 2, header)


def encode_stream_get() -> bytes:
    """Request the Stream device's latest quotas/configuration."""
    header = b"".join((
        _field(2, 0, 32), _field(3, 0, 32),
        _field(14, 0, int(time.time() * 1000)), _field(23, 2, b"ios"),
    ))
    return _field(1, 2, header)


def encode_stream_command(serial: str, key: str, value, current_values: dict | None = None) -> bytes:
    """Encode the common Stream Ultra/AC Pro DisplayPropertyUpload writes."""
    field_numbers = {
        # ConfigWrite uses different field numbers than DisplayPropertyUpload.
        "relay2Onoff": 380, "relay3Onoff": 381, "powConsumptionMeasurement": 239,
        "backupReverseSoc": 102, "cmsMinDsgSoc": 34, "cmsMaxChgSoc": 33,
    }
    current_values = current_values or {}
    if key == "loadPower1":
        load_fields = []
        for field, state_key in ((1, "startMin1"), (2, "endMin1")):
            if current_values.get(state_key) is not None:
                load_fields.append(_field(field, 0, int(current_values[state_key])))
        load_fields.append(_field(3, 0, int(value)))
        pdata_fields = [_field(6, 0, int(time.time()))]
        if current_values.get("feedGridModePowLimit") is not None:
            pdata_fields.append(_field(169, 0, int(current_values["feedGridModePowLimit"])))
        pdata_fields.append(_field(379, 2, _field(1, 2, b"".join(load_fields))))
        pdata = b"".join(pdata_fields)
        data_len = len(pdata)
    elif key not in field_numbers:
        raise ValueError(f"unsupported Stream command: {key}")
    else:
        # The actual field number is device-specific and is large (up to 3 bytes
        # as a protobuf tag).
        pdata_fields = [_field(6, 0, int(time.time()))]
        if key == "cmsMaxChgSoc" and current_values.get("cmsMinDsgSoc") is not None:
            pdata_fields.append(_field(field_numbers[key], 0, int(value)))
            pdata_fields.append(_field(34, 0, int(current_values["cmsMinDsgSoc"])))
        elif key == "cmsMinDsgSoc" and current_values.get("cmsMaxChgSoc") is not None:
            pdata_fields.append(_field(33, 0, int(current_values["cmsMaxChgSoc"])))
            pdata_fields.append(_field(field_numbers[key], 0, int(value)))
        else:
            pdata_fields.append(_field(field_numbers[key], 0, int(value)))
        pdata = b"".join(pdata_fields)
        data_len = 9 if key not in {"cmsMinDsgSoc", "cmsMaxChgSoc"} else 12
    header = b"".join((
        _field(2, 0, 32), _field(3, 0, 2), _field(4, 0, 1), _field(5, 0, 1),
        _field(8, 0, 254), _field(9, 0, 17), _field(10, 0, data_len),
        _field(11, 0, 1), _field(14, 0, int(time.time() * 1000)), _field(15, 0, 56),
        _field(16, 0, 3), _field(17, 0, 1), _field(23, 2, b"Android"),
        _field(25, 2, serial.encode()), _field(1, 2, pdata),
    ))
    return _field(1, 2, header)
