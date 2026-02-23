import h3

H3_RESOLUTION = 7


def latlng_to_h3(lat: float, lon: float, resolution: int = H3_RESOLUTION) -> str:
    return h3.latlng_to_cell(lat, lon, resolution)


def h3_to_center(h3_index: str) -> tuple[float, float]:
    lat, lon = h3.cell_to_latlng(h3_index)
    return lat, lon


def get_h3_neighbors(h3_index: str, k: int = 1) -> list[str]:
    return list(h3.grid_disk(h3_index, k))
