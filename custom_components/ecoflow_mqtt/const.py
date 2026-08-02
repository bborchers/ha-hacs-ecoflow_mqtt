DOMAIN = "ecoflow_mqtt"
CONF_USER_ID = "user_id"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_CLIENT_ID = "client_id"
CONF_BROKER = "broker"
CONF_PORT = "port"
CONF_DEVICES = "devices"
DEFAULT_BROKER = "mqtt-e.ecoflow.com"
DEFAULT_PORT = 8883

PLATFORMS = ["sensor", "switch", "number"]

# These are the stable JSON telemetry keys used by the Delta/River families
# in the original ioBroker adapter. Values are converted using the same scale.
SENSORS = {
    "soc": ("Battery", "%", "battery", 1),
    "f32ShowSoc": ("Battery", "%", "battery", 1),
    "inputWatts": ("Input power", "W", "power", 0.1),
    "outputWatts": ("Output power", "W", "power", 0.1),
    "acInVol": ("AC input voltage", "V", "voltage", 0.001),
    "invOutVol": ("AC output voltage", "V", "voltage", 0.001),
    "acInAmp": ("AC input current", "A", "current", 0.001),
    "invOutAmp": ("AC output current", "A", "current", 0.001),
    "dcInVol": ("DC input voltage", "V", "voltage", 0.001),
    "temp": ("Temperature", "°C", "temperature", 1),
    "outTemp": ("Inverter temperature", "°C", "temperature", 1),
    "cycles": ("Charge cycles", "cycles", None, 1),
    "remainTime": ("Remaining time", "min", "duration", 1),
    "maxChgSoc": ("Maximum charge", "%", None, 1),
    "minDsgSoc": ("Minimum discharge", "%", None, 1),
}

SWITCHES = {
    "cfgAcEnabled": ("AC output", "mppt"),
    "dcOutState": ("DC output", "pd"),
    "carState": ("Car output", "mppt"),
    "cfgAcXboost": ("X-Boost", "mppt"),
}

NUMBERS = {
    "maxChgSoc": ("Maximum charge", "%", 50, 100, 1, "ems"),
    "minDsgSoc": ("Minimum discharge", "%", 0, 100, 1, "ems"),
    "cfgChgWatts": ("AC charging power", "W", 0, 2400, 1, "mppt"),
}

PROTOBUF_TYPES = {
    "pstream", "pstream600", "pstream800", "plug", "delta3", "delta3plus",
    "delta3classic", "delta3maxplus", "deltapro3", "deltaproultra", "river3",
    "river3plus", "powerocean", "poweroceanplus", "poweroceanfit", "panel2",
    "alternator", "smartmeter", "stream_ac", "stream_ac_pro", "stream_pro",
    "stream_ultra", "stream_ultra_x", "stream_inverter", "wave3", "glacier55",
    "rapidpro320", "unknown",
}

PROTO_SENSORS = {
    "pv1InputVolt": ("PV1 input voltage", "V", "voltage", 1),
    "pv1InputWatts": ("PV1 input power", "W", "power", 1),
    "pv2InputVolt": ("PV2 input voltage", "V", "voltage", 1),
    "pv2InputWatts": ("PV2 input power", "W", "power", 1),
    "batInputVolt": ("Battery voltage", "V", "voltage", 1),
    "batInputWatts": ("Battery power", "W", "power", 1),
    "batSoc": ("Battery state of charge", "%", "battery", 1),
    "invOutputWatts": ("Inverter output power", "W", "power", 1),
    "invOutputCur": ("Inverter output current", "A", "current", 1),
    "invTemp": ("Inverter temperature", "°C", "temperature", 1),
    "permanentWatts": ("Permanent output", "W", "power", 1),
    "ratedPower": ("Rated power", "W", "power", 1),
    "lowerLimit": ("Battery lower limit", "%", None, 1),
    "upperLimit": ("Battery upper limit", "%", None, 1),
    "batChargingTime": ("Battery charging time", "min", "duration", 1),
    "batDischargingTime": ("Battery discharging time", "min", "duration", 1),
    "wifi_rssi": ("Wi-Fi signal", "dBm", "signal_strength", 1),
}

PROTO_SWITCHES = {
    "supplyPriority": ("Supply priority", "inverter_heartbeat"),
    "feedPriority": ("Feed priority", "inverter_heartbeat"),
}

PROTO_NUMBERS = {
    "permanentWatts": ("Permanent output", "W", 0, 800, 1, "inverter_heartbeat"),
    "lowerLimit": ("Battery lower limit", "%", 0, 100, 1, "inverter_heartbeat"),
    "upperLimit": ("Battery upper limit", "%", 0, 100, 1, "inverter_heartbeat"),
}

STREAM_SENSORS = {
    "bmsBattSoc": ("Battery state of charge", "%", "battery", 1),
    "bmsBattSoh": ("Battery state of health", "%", "battery", 1),
    "cmsBattSoc": ("Overall battery state of charge", "%", "battery", 1),
    "cmsBattSoh": ("Overall battery state of health", "%", "battery", 1),
    "powGetPv": ("PV power", "W", "power", 1),
    "powGetPv2": ("PV2 power", "W", "power", 1),
    "powGetPv3": ("PV3 power", "W", "power", 1),
    "powGetPv4": ("PV4 power", "W", "power", 1),
    "powGetPvSum": ("Total PV power", "W", "power", 1),
    "powGetSysGrid": ("Grid power", "W", "power", 1),
    "powGetSysLoad": ("Load power", "W", "power", 1),
    "powGetBpCms": ("Battery power", "W", "power", 1),
    "gridConnectionVol": ("Grid voltage", "V", "voltage", 1),
    "gridConnectionAmp": ("Grid current", "A", "current", 1),
    "gridConnectionFreq": ("Grid frequency", "Hz", "frequency", 1),
    "gridConnectionPower": ("Grid connection power", "W", "power", 1),
    "sysGridConnectionPower": ("System grid power", "W", "power", 1),
    "socketMeasurePower": ("Socket power", "W", "power", 1),
    "feedGridModePowLimit": ("Feed-in power limit", "W", "power", 1),
    "bmsDsgRemTime": ("Battery discharge time", "min", "duration", 1),
    "bmsChgRemTime": ("Battery charge time", "min", "duration", 1),
    "cmsDsgRemTime": ("System discharge time", "min", "duration", 1),
    "cmsChgRemTime": ("System charge time", "min", "duration", 1),
    "cmsMaxChgSoc": ("Maximum charge", "%", None, 1),
    "cmsMinDsgSoc": ("Minimum discharge", "%", None, 1),
    "backupReverseSoc": ("Backup reserve", "%", None, 1),
    "gridConnectionPower": ("Grid connection power", "W", "power", 1),
}

STREAM_SWITCHES = {
    "relay2Onoff": ("AC output relay 2", "DisplayPropertyUpload"),
    "relay3Onoff": ("AC output relay 3", "DisplayPropertyUpload"),
}

STREAM_NUMBERS = {
    "cmsMaxChgSoc": ("Maximum charge", "%", 0, 100, 1, "DisplayPropertyUpload"),
    "cmsMinDsgSoc": ("Minimum discharge", "%", 0, 100, 1, "DisplayPropertyUpload"),
    "backupReverseSoc": ("Backup reserve", "%", 0, 100, 1, "DisplayPropertyUpload"),
    "powConsumptionMeasurement": ("Consumption measurement", "W", 0, 10000, 1, "DisplayPropertyUpload"),
    "loadPower1": ("Base load power (partial automatic)", "W", 0, 1200, 10, "ConfigWrite"),
}
