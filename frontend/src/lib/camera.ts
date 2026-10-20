export type CameraError =
  | 'insecure'
  | 'unsupported'
  | 'denied'
  | 'no_camera'
  | 'in_use'
  | 'unknown';

/** Rear camera, with plain-language failure reasons (SRS §2.4.5). */
export async function openRearCamera(): Promise<MediaStream> {
  if (!window.isSecureContext) throw { camera: 'insecure' as CameraError };
  if (!navigator.mediaDevices?.getUserMedia) throw { camera: 'unsupported' as CameraError };
  try {
    return await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });
  } catch (e) {
    const name = (e as DOMException)?.name;
    const camera: CameraError =
      name === 'NotAllowedError' || name === 'SecurityError'
        ? 'denied'
        : name === 'NotFoundError' || name === 'OverconstrainedError'
          ? 'no_camera'
          : name === 'NotReadableError' || name === 'AbortError'
            ? 'in_use'
            : 'unknown';
    throw { camera };
  }
}

export function cameraErrorCode(e: unknown): CameraError {
  return (e as { camera?: CameraError })?.camera ?? 'unknown';
}

/** Current video frame as JPEG (~960 px wide, quality 0.7 — HANDOFF §7.3). */
export function grabJpeg(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  width = 960,
): Promise<Blob | null> {
  if (!video.videoWidth) return Promise.resolve(null);
  const scale = Math.min(1, width / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext('2d')!.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.7));
}

/** Keep the screen on while capturing; re-acquired when the tab becomes visible again. */
export class ScreenWakeLock {
  private lock: WakeLockSentinel | null = null;
  private wanted = false;
  private onVisible = () => {
    if (this.wanted && document.visibilityState === 'visible') void this.acquire();
  };

  async acquire(): Promise<void> {
    this.wanted = true;
    document.addEventListener('visibilitychange', this.onVisible);
    try {
      this.lock = (await navigator.wakeLock?.request('screen')) ?? null;
    } catch {
      /* not supported or denied: capture still works */
    }
  }

  release(): void {
    this.wanted = false;
    document.removeEventListener('visibilitychange', this.onVisible);
    void this.lock?.release().catch(() => undefined);
    this.lock = null;
  }
}
