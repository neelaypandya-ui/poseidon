/**
 * 4K Video Export utility.
 *
 * Captures the Deck.gl/MapLibre canvas using MediaRecorder API
 * and exports as WebM/MP4 video file.
 */

export interface VideoExportOptions {
  width: number
  height: number
  fps: number
  duration: number // seconds
  filename: string
}

const RESOLUTION_PRESETS = {
  '1080p': { width: 1920, height: 1080 },
  '1440p': { width: 2560, height: 1440 },
  '4K': { width: 3840, height: 2160 },
} as const

export type ResolutionPreset = keyof typeof RESOLUTION_PRESETS

export function getResolution(preset: ResolutionPreset) {
  return RESOLUTION_PRESETS[preset]
}

export async function exportCanvasVideo(
  canvas: HTMLCanvasElement,
  options: VideoExportOptions,
  onProgress?: (pct: number) => void,
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const stream = canvas.captureStream(options.fps)

    // Try VP9 first, fall back to VP8
    const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9'
      : MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
      ? 'video/webm;codecs=vp8'
      : 'video/webm'

    const recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 20_000_000, // 20 Mbps for high quality
    })

    const chunks: Blob[] = []

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunks.push(e.data)
      }
    }

    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType })
      resolve(blob)
    }

    recorder.onerror = (e) => {
      reject(new Error(`Recording failed: ${e}`))
    }

    // Start recording
    recorder.start(100) // Collect data every 100ms

    // Progress tracking
    const totalMs = options.duration * 1000
    const startTime = Date.now()
    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime
      const pct = Math.min(100, (elapsed / totalMs) * 100)
      onProgress?.(pct)
    }, 200)

    // Stop after duration
    setTimeout(() => {
      clearInterval(progressInterval)
      recorder.stop()
      onProgress?.(100)
    }, totalMs)
  })
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
