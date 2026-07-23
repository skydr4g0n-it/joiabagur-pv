import jsQR from 'jsqr';

export interface DecodeResult {
  value: string;
  type: 'barcode' | 'qr';
}

export class BarcodeScanningService {
  private mediaStream: MediaStream | null = null;
  private animationFrameId: number | null = null;
  private isScanning = false;
  private lastDecodeTime = 0;
  private lastDecodedValue: string | null = null;

  isCompatible(): boolean {
    return !!(navigator.mediaDevices?.getUserMedia);
  }

  async startCamera(videoElement: HTMLVideoElement): Promise<void> {
    if (this.mediaStream) {
      this.stopCamera();
    }

    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'environment',
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });

    videoElement.srcObject = this.mediaStream;
    await videoElement.play();
  }

  stopCamera(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    this.isScanning = false;
    this.lastDecodedValue = null;
    this.lastDecodeTime = 0;
  }

  async scanBarcode(
    canvasElement: HTMLCanvasElement,
    videoElement: HTMLVideoElement,
  ): Promise<DecodeResult | null> {
    const result = this.captureFrame(canvasElement, videoElement);
    if (!result) return null;

    const { imageData } = result;

    try {
      const { default: Quagga } = await import('@ericblade/quagga2');

      return new Promise<DecodeResult | null>((resolve) => {
        Quagga.decodeSingle(
          {
            decoder: { readers: ['code_128_reader', 'ean_reader', 'ean_8_reader', 'upc_reader', 'code_39_reader'] },
            locate: true,
            src: imageData as any,
          },
          (result: any) => {
            if (result?.codeResult?.code) {
              resolve({ value: result.codeResult.code, type: 'barcode' });
            } else {
              resolve(null);
            }
          },
        );
      });
    } catch {
      return null;
    }
  }

  async scanQrCode(
    canvasElement: HTMLCanvasElement,
    videoElement: HTMLVideoElement,
  ): Promise<DecodeResult | null> {
    const result = this.captureFrame(canvasElement, videoElement);
    if (!result) return null;

    const qrCode = jsQR(result.imageData.data, result.imageData.width, result.imageData.height);
    if (qrCode?.data) {
      return { value: qrCode.data, type: 'qr' };
    }

    return null;
  }

  continuousScan(
    videoElement: HTMLVideoElement,
    canvasElement: HTMLCanvasElement,
    onDecode: (result: DecodeResult) => void,
    debounceMs = 2000,
  ): void {
    if (this.isScanning) return;
    this.isScanning = true;

    const decodeLoop = async () => {
      if (!this.isScanning) return;

      const now = Date.now();
      if (now - this.lastDecodeTime >= debounceMs) {
        const result =
          (await this.scanQrCode(canvasElement, videoElement)) ||
          (await this.scanBarcode(canvasElement, videoElement));

        if (result && result.value !== this.lastDecodedValue) {
          this.lastDecodedValue = result.value;
          this.lastDecodeTime = now;
          onDecode(result);
        }
      }

      this.animationFrameId = requestAnimationFrame(decodeLoop);
    };

    this.animationFrameId = requestAnimationFrame(decodeLoop);
  }

  stopContinuousScan(): void {
    this.isScanning = false;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  async toggleFlash(videoElement: HTMLVideoElement): Promise<boolean> {
    if (!this.mediaStream) return false;

    const track = this.mediaStream.getVideoTracks()[0];
    if (!track) return false;

    const capabilities = track.getCapabilities();
    if (!capabilities.torch) return false;

    const currentTorch = track.getSettings().torch;
    try {
      await track.applyConstraints({
        advanced: [{ torch: !currentTorch }],
      });
      return !currentTorch;
    } catch {
      return false;
    }
  }

  resetDecodeHistory(): void {
    this.lastDecodedValue = null;
    this.lastDecodeTime = 0;
  }

  private captureFrame(
    canvasElement: HTMLCanvasElement,
    videoElement: HTMLVideoElement,
  ): { imageData: ImageData } | null {
    const canvas = canvasElement;
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    return { imageData };
  }
}
