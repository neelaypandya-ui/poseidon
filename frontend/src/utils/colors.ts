// Vessel type color mapping (RGBA)
export const VESSEL_COLORS: Record<string, [number, number, number, number]> = {
  tanker:    [245, 158, 11, 220],   // amber
  cargo:     [6, 182, 212, 220],    // cyan
  fishing:   [34, 197, 94, 220],    // green
  passenger: [168, 85, 247, 220],   // purple
  tug:       [249, 115, 22, 220],   // orange
  pleasure:  [236, 72, 153, 220],   // pink
  military:  [220, 38, 38, 220],    // red
  sar:       [234, 179, 8, 220],    // yellow
  hsc:       [59, 130, 246, 220],   // blue
  unknown:   [239, 68, 68, 200],    // red (dimmer)
}

export function getVesselColor(shipType: string): [number, number, number, number] {
  return VESSEL_COLORS[shipType] || VESSEL_COLORS.unknown
}

// Speed-based trail color (brighter = faster)
export function getSpeedColor(sog: number | null): [number, number, number, number] {
  if (sog === null || sog === undefined) return [100, 100, 100, 150]
  const t = Math.min(sog / 20, 1) // normalize to 0-1 (20 knots = max brightness)
  const r = Math.round(50 + t * 200)
  const g = Math.round(150 + t * 105)
  const b = Math.round(255)
  return [r, g, b, 200]
}
