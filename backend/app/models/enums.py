from enum import Enum


class VesselType(str, Enum):
    CARGO = "cargo"
    TANKER = "tanker"
    FISHING = "fishing"
    PASSENGER = "passenger"
    TUG = "tug"
    PLEASURE = "pleasure"
    MILITARY = "military"
    SAR = "sar"
    HSC = "hsc"
    UNKNOWN = "unknown"


class NavStatus(str, Enum):
    UNDER_WAY_USING_ENGINE = "under_way_using_engine"
    AT_ANCHOR = "at_anchor"
    NOT_UNDER_COMMAND = "not_under_command"
    RESTRICTED_MANOEUVRABILITY = "restricted_manoeuvrability"
    CONSTRAINED_BY_DRAUGHT = "constrained_by_draught"
    MOORED = "moored"
    AGROUND = "aground"
    ENGAGED_IN_FISHING = "engaged_in_fishing"
    UNDER_WAY_SAILING = "under_way_sailing"
    RESERVED_HSC = "reserved_hsc"
    RESERVED_WING = "reserved_wing"
    POWER_DRIVEN_TOWING_ASTERN = "power_driven_towing_astern"
    POWER_DRIVEN_PUSHING = "power_driven_pushing"
    RESERVED_13 = "reserved_13"
    AIS_SART = "ais_sart"
    NOT_DEFINED = "not_defined"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


# AIS type code to VesselType mapping
def ais_type_to_vessel_type(code: int | None) -> VesselType:
    if code is None:
        return VesselType.UNKNOWN
    if 70 <= code <= 79:
        return VesselType.CARGO
    if 80 <= code <= 89:
        return VesselType.TANKER
    if code == 30:
        return VesselType.FISHING
    if 60 <= code <= 69:
        return VesselType.PASSENGER
    if 31 <= code <= 32:
        return VesselType.TUG
    if 36 <= code <= 37:
        return VesselType.PLEASURE
    if 35 == code:
        return VesselType.MILITARY
    if code == 51:
        return VesselType.SAR
    if 40 <= code <= 49:
        return VesselType.HSC
    return VesselType.UNKNOWN


# AIS navigational status code to NavStatus mapping
NAV_STATUS_MAP: dict[int, NavStatus] = {
    0: NavStatus.UNDER_WAY_USING_ENGINE,
    1: NavStatus.AT_ANCHOR,
    2: NavStatus.NOT_UNDER_COMMAND,
    3: NavStatus.RESTRICTED_MANOEUVRABILITY,
    4: NavStatus.CONSTRAINED_BY_DRAUGHT,
    5: NavStatus.MOORED,
    6: NavStatus.AGROUND,
    7: NavStatus.ENGAGED_IN_FISHING,
    8: NavStatus.UNDER_WAY_SAILING,
    9: NavStatus.RESERVED_HSC,
    10: NavStatus.RESERVED_WING,
    11: NavStatus.POWER_DRIVEN_TOWING_ASTERN,
    12: NavStatus.POWER_DRIVEN_PUSHING,
    13: NavStatus.RESERVED_13,
    14: NavStatus.AIS_SART,
    15: NavStatus.NOT_DEFINED,
}
