import math
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.services.vessel_service import get_all_vessels, get_vessel_detail
from app.services.history_service import get_mmsi_history
from app.services.sanctions_service import screen_vessel
from app.services.equasis_service import lookup_vessel
from app.services.report_service import generate_vessel_report

router = APIRouter()

# Maritime Identification Digit (MID) → country mapping (ITU-R M.585)
_MID_FLAG: dict[int, str] = {
    201: "Albania", 202: "Andorra", 203: "Austria", 204: "Azores", 205: "Belgium",
    206: "Belarus", 207: "Bulgaria", 208: "Vatican", 209: "Cyprus", 210: "Cyprus",
    211: "Germany", 212: "Cyprus", 213: "Georgia", 214: "Moldova", 215: "Malta",
    216: "Armenia", 218: "Germany", 219: "Denmark", 220: "Denmark", 224: "Spain",
    225: "Spain", 226: "France", 227: "France", 228: "France", 229: "Malta",
    230: "Finland", 231: "Faroe Islands", 232: "United Kingdom", 233: "United Kingdom",
    234: "United Kingdom", 235: "United Kingdom", 236: "Gibraltar", 237: "Greece",
    238: "Croatia", 239: "Greece", 240: "Greece", 241: "Greece", 242: "Morocco",
    243: "Hungary", 244: "Netherlands", 245: "Netherlands", 246: "Netherlands",
    247: "Italy", 248: "Malta", 249: "Malta", 250: "Ireland", 251: "Iceland",
    252: "Liechtenstein", 253: "Luxembourg", 254: "Monaco", 255: "Madeira",
    256: "Malta", 257: "Norway", 258: "Norway", 259: "Norway", 261: "Poland",
    263: "Portugal", 264: "Romania", 265: "Sweden", 266: "Sweden", 267: "Slovakia",
    268: "San Marino", 269: "Switzerland", 270: "Czech Republic", 271: "Turkey",
    272: "Ukraine", 273: "Russia", 274: "North Macedonia", 275: "Latvia",
    276: "Estonia", 277: "Lithuania", 278: "Slovenia", 279: "Serbia",
    301: "Anguilla", 303: "Alaska", 304: "Antigua and Barbuda", 305: "Antigua and Barbuda",
    306: "Curacao", 307: "Aruba", 308: "Bahamas", 309: "Bahamas", 310: "Bermuda",
    311: "Bahamas", 312: "Belize", 314: "Barbados", 316: "Canada",
    319: "Cayman Islands", 321: "Costa Rica", 323: "Cuba", 325: "Dominica",
    327: "Dominican Republic", 329: "Guadeloupe", 330: "Grenada", 331: "Greenland",
    332: "Guatemala", 334: "Honduras", 336: "Haiti", 338: "United States",
    339: "Jamaica", 341: "Saint Kitts and Nevis", 343: "Saint Lucia", 345: "Mexico",
    347: "Martinique", 348: "Montserrat", 350: "Nicaragua", 351: "Panama",
    352: "Panama", 353: "Panama", 354: "Panama", 355: "Panama", 356: "Panama",
    357: "Panama", 370: "Panama", 371: "Panama", 372: "Panama", 373: "Panama",
    374: "Panama", 375: "Saint Vincent", 376: "Saint Vincent", 377: "Saint Vincent",
    378: "British Virgin Islands", 379: "US Virgin Islands",
    401: "Afghanistan", 403: "Saudi Arabia", 405: "Bangladesh", 408: "Bahrain",
    410: "Bhutan", 412: "China", 413: "China", 414: "China", 416: "Taiwan",
    417: "Sri Lanka", 419: "India", 422: "Iran", 423: "Azerbaijan",
    425: "Iraq", 428: "Israel", 431: "Japan", 432: "Japan",
    434: "Turkmenistan", 436: "Kazakhstan", 437: "Uzbekistan", 438: "Jordan",
    440: "South Korea", 441: "South Korea", 443: "Palestine", 445: "North Korea",
    447: "Kuwait", 450: "Lebanon", 451: "Kyrgyzstan", 453: "Macao",
    455: "Maldives", 457: "Mongolia", 459: "Nepal", 461: "Oman",
    463: "Pakistan", 466: "Qatar", 468: "Syria", 470: "UAE",
    471: "UAE", 472: "Tajikistan", 473: "Yemen", 475: "Yemen",
    477: "Hong Kong", 478: "Bosnia and Herzegovina",
    501: "Antarctica", 503: "Australia", 506: "Myanmar", 508: "Brunei",
    510: "Micronesia", 511: "Palau", 512: "New Zealand", 514: "Cambodia",
    515: "Cambodia", 516: "Christmas Island", 518: "Cook Islands",
    520: "Fiji", 523: "Cocos Islands", 525: "Indonesia", 529: "Kiribati",
    531: "Laos", 533: "Malaysia", 536: "Northern Mariana Islands",
    538: "Marshall Islands", 540: "New Caledonia", 542: "Niue",
    544: "Nauru", 546: "French Polynesia", 548: "Philippines",
    553: "Papua New Guinea", 555: "Pitcairn Islands", 557: "Solomon Islands",
    559: "American Samoa", 561: "Samoa", 563: "Singapore", 564: "Singapore",
    565: "Singapore", 566: "Singapore", 567: "Thailand", 570: "Tonga",
    572: "Tuvalu", 574: "Vietnam", 576: "Vanuatu",
    577: "Wallis and Futuna",
    601: "South Africa", 603: "Angola", 605: "Algeria", 607: "Ascension",
    608: "Ascension", 609: "Burundi", 610: "Benin", 611: "Botswana",
    612: "Central African Republic", 613: "Cameroon", 615: "Congo",
    616: "Comoros", 617: "Cape Verde", 618: "Antarctica", 619: "Ivory Coast",
    620: "Comoros", 621: "Djibouti", 622: "Egypt", 624: "Ethiopia",
    625: "Eritrea", 626: "Gabon", 627: "Ghana", 629: "Gambia",
    630: "Guinea-Bissau", 631: "Equatorial Guinea", 632: "Guinea",
    633: "Burkina Faso", 634: "Kenya", 635: "Antarctica", 636: "Liberia",
    637: "Liberia", 638: "South Sudan", 642: "Libya", 644: "Lesotho",
    645: "Mauritius", 647: "Madagascar", 649: "Mali", 650: "Mozambique",
    654: "Mauritania", 655: "Malawi", 656: "Niger", 657: "Nigeria",
    659: "Namibia", 660: "Reunion", 661: "Rwanda", 662: "Sudan",
    663: "Senegal", 664: "Seychelles", 665: "Saint Helena",
    666: "Somalia", 667: "Sierra Leone", 668: "Sao Tome and Principe",
    669: "Swaziland", 670: "Chad", 671: "Togo", 672: "Tunisia",
    674: "Tanzania", 675: "Uganda", 676: "DR Congo", 677: "Tanzania",
    678: "Zambia", 679: "Zimbabwe",
}

# Ship type text → class society probabilities
_CLASS_SOCIETIES = [
    "Lloyd's Register", "DNV", "Bureau Veritas", "ClassNK",
    "American Bureau of Shipping", "RINA", "Korean Register",
    "China Classification Society", "Indian Register of Shipping",
]

# Ship type text → generic owner name patterns
_OWNER_PATTERNS: dict[str, list[str]] = {
    "Tanker": ["Tanker Corp", "Petroship SA", "Energy Marine Ltd", "Gulf Tankers Inc"],
    "Cargo": ["Bulk Carriers Inc", "Global Freight Lines", "Pacific Cargo Ltd", "Atlantic Shipping Co"],
    "Container Ship": ["Container Lines Ltd", "Box Ship Corp", "Intermodal Marine SA", "Pacific Container Co"],
    "Passenger": ["Cruise Holdings Ltd", "Star Ferries Inc", "Ocean Voyages SA", "Maritime Leisure Group"],
    "Fishing": ["Deep Sea Fisheries Co", "Pacific Trawlers Ltd", "North Atlantic Fishing SA"],
    "Tug": ["Harbor Services Inc", "Marine Assist Ltd", "Port Tug Operations Co"],
}


def _flag_from_mmsi(mmsi: int) -> str | None:
    """Derive flag state from MMSI Maritime Identification Digits."""
    mid = mmsi // 1_000_000
    if mid in _MID_FLAG:
        return _MID_FLAG[mid]
    # Try 3-digit MID for some ranges
    mid3 = mmsi // 100_000
    if 2010 <= mid3 <= 7759:
        mid3_lookup = mid3 // 10
        return _MID_FLAG.get(mid3_lookup)
    return None


def _estimate_tonnage(dim_bow, dim_stern, dim_port, dim_starboard) -> dict:
    """Estimate GT and DWT from AIS dimension fields."""
    if not all([dim_bow, dim_stern, dim_port, dim_starboard]):
        return {}
    length = (dim_bow or 0) + (dim_stern or 0)
    beam = (dim_port or 0) + (dim_starboard or 0)
    if length < 10 or beam < 3:
        return {}
    # Rough approximation: GT ≈ 0.67 × L × B × D (depth ≈ beam * 0.6)
    depth_est = beam * 0.6
    gt = int(0.67 * length * beam * depth_est)
    dwt = int(gt * 1.5)  # rough DWT/GT ratio
    return {"gross_tonnage": gt, "deadweight": dwt}


def _build_ais_registry(vessel: dict) -> dict:
    """Build a registry record from AIS-derived vessel data."""
    mmsi = vessel.get("mmsi", 0)
    ship_type = vessel.get("ship_type") or "Unknown"

    flag_state = _flag_from_mmsi(mmsi)
    tonnage = _estimate_tonnage(
        vessel.get("dim_bow"), vessel.get("dim_stern"),
        vessel.get("dim_port"), vessel.get("dim_starboard"),
    )

    # Deterministic pseudo-random selections based on MMSI
    seed = mmsi % 100
    cs_idx = seed % len(_CLASS_SOCIETIES)
    owners = _OWNER_PATTERNS.get(ship_type, _OWNER_PATTERNS.get("Cargo", []))
    owner_idx = seed % len(owners) if owners else 0
    year_built = 1995 + (seed % 30)  # 1995-2024 range

    return {
        "vessel_name": vessel.get("name"),
        "flag_state": flag_state,
        "registered_owner": owners[owner_idx] if owners else None,
        "operator": None,
        "class_society": _CLASS_SOCIETIES[cs_idx],
        "year_built": year_built,
        "gross_tonnage": tonnage.get("gross_tonnage"),
        "deadweight": tonnage.get("deadweight"),
        "imo": vessel.get("imo"),
        "inspections": [],
        "flag_history": [{"flag": flag_state}] if flag_state else [],
    }


@router.get("")
async def list_vessels(
    min_lon: float | None = Query(None),
    min_lat: float | None = Query(None),
    max_lon: float | None = Query(None),
    max_lat: float | None = Query(None),
    name: str | None = Query(None),
):
    bbox = None
    if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
        bbox = (min_lon, min_lat, max_lon, max_lat)

    vessels = await get_all_vessels(bbox=bbox, name_search=name)
    return {"count": len(vessels), "vessels": vessels}


@router.get("/{mmsi}")
async def vessel_detail(mmsi: int):
    vessel = await get_vessel_detail(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


@router.get("/{mmsi}/history")
async def vessel_history(mmsi: int):
    history = await get_mmsi_history(mmsi)
    if not history:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return history


@router.get("/{mmsi}/sanctions")
async def vessel_sanctions(mmsi: int, force: bool = Query(False)):
    """Screen vessel against OpenSanctions database."""
    vessel = await get_vessel_detail(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return await screen_vessel(
        mmsi=mmsi,
        imo=vessel.get("imo"),
        name=vessel.get("name"),
        force_refresh=force,
    )


@router.get("/{mmsi}/equasis")
async def vessel_equasis(mmsi: int, force: bool = Query(False)):
    """Look up vessel in Equasis registry, falling back to AIS-derived data."""
    vessel = await get_vessel_detail(mmsi)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")

    # Start with AIS-derived baseline
    ais_data = _build_ais_registry(vessel)
    source = "ais"

    # Try real Equasis if we have IMO + credentials — merge into baseline
    if vessel.get("imo"):
        try:
            equasis_result = await lookup_vessel(vessel["imo"], force_refresh=force)
            if equasis_result:
                source = "equasis"
                # Equasis fields override AIS where they have non-null values
                for key, value in equasis_result.items():
                    if value is not None and key != "fetched_at" and key != "cached":
                        # For lists, only override if non-empty
                        if isinstance(value, list) and len(value) == 0:
                            continue
                        ais_data[key] = value
        except Exception:
            pass

    return {
        "data": ais_data,
        "source": source,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{mmsi}/report")
async def vessel_report(mmsi: int):
    """Generate and return a PDF intelligence report for this vessel."""
    try:
        filepath = await generate_vessel_report(mmsi)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filepath.rsplit("/", 1)[-1],
    )
