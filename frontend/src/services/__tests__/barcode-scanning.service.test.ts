import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { BarcodeScanningService } from '../barcode-scanning.service';

describe('BarcodeScanningService', () => {
  let service: BarcodeScanningService;

  beforeEach(() => {
    service = new BarcodeScanningService();
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn(),
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('startCamera', () => {
    it('should start video stream when getUserMedia succeeds', async () => {
      const mockStream = {
        getTracks: () => [{ stop: vi.fn() }],
        getVideoTracks: () => [{ stop: vi.fn(), getCapabilities: vi.fn(), getSettings: vi.fn(), applyConstraints: vi.fn() }],
      };
      vi.mocked(navigator.mediaDevices.getUserMedia).mockResolvedValue(mockStream as any);

      const videoElement = document.createElement('video');
      videoElement.play = vi.fn().mockResolvedValue(undefined);

      await service.startCamera(videoElement);

      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
        video: {
          facingMode: 'environment',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      expect(videoElement.srcObject).toBe(mockStream);
    });

    it('should throw when getUserMedia fails', async () => {
      vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(new Error('Permission denied'));

      const videoElement = document.createElement('video');

      await expect(service.startCamera(videoElement)).rejects.toThrow('Permission denied');
    });
  });

  describe('stopCamera', () => {
    it('should stop all tracks and clean up', async () => {
      const stopTrack1 = vi.fn();
      const stopTrack2 = vi.fn();
      const mockStream = {
        getTracks: () => [{ stop: stopTrack1 }, { stop: stopTrack2 }],
        getVideoTracks: () => [{ stop: vi.fn(), getCapabilities: vi.fn(), getSettings: vi.fn(), applyConstraints: vi.fn() }],
      };
      vi.mocked(navigator.mediaDevices.getUserMedia).mockResolvedValue(mockStream as any);

      const videoElement = document.createElement('video');
      videoElement.play = vi.fn().mockResolvedValue(undefined);
      await service.startCamera(videoElement);

      service.stopCamera();

      expect(stopTrack1).toHaveBeenCalled();
      expect(stopTrack2).toHaveBeenCalled();
    });
  });

  describe('isCompatible', () => {
    it('should return true when getUserMedia is available', () => {
      expect(service.isCompatible()).toBe(true);
    });

    it('should return false when getUserMedia is not available', () => {
      vi.stubGlobal('navigator', {});
      const newService = new BarcodeScanningService();
      expect(newService.isCompatible()).toBe(false);
    });
  });

  describe('toggleFlash', () => {
    it('should return false when no media stream', async () => {
      const result = await service.toggleFlash(document.createElement('video'));
      expect(result).toBe(false);
    });
  });

  describe('scanQrCode', () => {
    it('should return null when canvas context is unavailable', async () => {
      const canvas = document.createElement('canvas');
      const video = document.createElement('video');

      const result = await service.scanQrCode(canvas, video);

      expect(result).toBeNull();
    });
  });

  describe('scanBarcode', () => {
    it('should return null when canvas context is unavailable', async () => {
      const canvas = document.createElement('canvas');
      const video = document.createElement('video');

      const result = await service.scanBarcode(canvas, video);

      expect(result).toBeNull();
    });
  });
});
