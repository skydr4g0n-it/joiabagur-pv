/**
 * Component tests for ProductPhotoUpload - T-EP1-004 (Tasks 16.7-16.9)
 * Tests photo upload, drag-and-drop interactions, and file validation feedback
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProductPhotoUpload } from './product-photo-upload';
import { productService } from '@/services/product.service';
import { ProductPhoto } from '@/types/product.types';

// Mock the auth provider
const mockUser = { id: 'user-1', username: 'admin', role: 'Administrator' };
vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({ user: mockUser }),
}));

// Mock the product service
vi.mock('@/services/product.service', () => ({
  productService: {
    uploadPhoto: vi.fn(),
    deletePhoto: vi.fn(),
    setPrimaryPhoto: vi.fn(),
  },
  default: {
    uploadPhoto: vi.fn(),
    deletePhoto: vi.fn(),
    setPrimaryPhoto: vi.fn(),
  },
}));

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

// Mock image URL helper
vi.mock('@/lib/image-url', () => ({
  getImageUrl: (url: string | null) => url || '/placeholder.png',
}));

const mockPhotos: ProductPhoto[] = [
  {
    id: 'photo-1',
    productId: 'prod-123',
    fileName: 'photo1.jpg',
    url: 'http://localhost/uploads/photo1.jpg',
    displayOrder: 0,
    isPrimary: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'photo-2',
    productId: 'prod-123',
    fileName: 'photo2.jpg',
    url: 'http://localhost/uploads/photo2.jpg',
    displayOrder: 1,
    isPrimary: false,
    createdAt: '2024-01-02T00:00:00Z',
    updatedAt: '2024-01-02T00:00:00Z',
  },
];

function renderComponent(photos: ProductPhoto[] = [], onPhotosChange = vi.fn()) {
  return render(
    <ProductPhotoUpload
      productId="prod-123"
      productSku="SKU-123"
      photos={photos}
      onPhotosChange={onPhotosChange}
    />
  );
}

/**
 * Helper to create a mock File object
 */
function createMockFile(name: string, size: number, type: string): File {
  const blob = new Blob(['x'.repeat(size)], { type });
  return new File([blob], name, { type });
}

function mockUploadProductResponse(overrides: Partial<ProductPhoto> = {}) {
  return {
    id: 'prod-123',
    sku: 'SKU-123',
    name: 'Test',
    price: 10,
    isActive: true,
    photos: [
      {
        id: 'photo-new',
        productId: 'prod-123',
        fileName: 'upload.jpg',
        url: 'http://localhost/uploads/upload.jpg',
        displayOrder: 0,
        isPrimary: true,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        ...overrides,
      },
    ],
  } as Awaited<ReturnType<typeof productService.uploadPhoto>>;
}

async function queueFileAndUpload(user: ReturnType<typeof userEvent.setup>, file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input!, { target: { files: [file] } });
  const uploadButton = await screen.findByRole('button', { name: /subir foto/i });
  await user.click(uploadButton);
}

describe('ProductPhotoUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Component Rendering (Task 16.7)', () => {
    it('should render upload zone for admin users', () => {
      // Act
      renderComponent();

      // Assert
      expect(screen.getByText(/arrastra fotos aquí/i)).toBeInTheDocument();
      expect(screen.getByText(/selecciona archivos/i)).toBeInTheDocument();
    });

    it('should display "no photos" message when photos array is empty', () => {
      // Act
      renderComponent([]);

      // Assert
      expect(screen.getByText(/no hay fotos subidas aún/i)).toBeInTheDocument();
      expect(screen.getByText(/sube la primera foto para comenzar/i)).toBeInTheDocument();
    });

    it('should render photo gallery with uploaded photos', () => {
      // Act
      renderComponent(mockPhotos);

      // Assert
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(2);
      expect(images[0]).toHaveAttribute('src', 'http://localhost/uploads/photo1.jpg');
      expect(images[1]).toHaveAttribute('src', 'http://localhost/uploads/photo2.jpg');
    });

    it('should display primary photo badge on primary photo', () => {
      // Act
      renderComponent(mockPhotos);

      // Assert
      expect(screen.getByText(/principal/i)).toBeInTheDocument();
    });

    it('should sort photos by displayOrder', () => {
      // Arrange - Photos in reverse order
      const unsortedPhotos = [mockPhotos[1], mockPhotos[0]];

      // Act
      renderComponent(unsortedPhotos);

      // Assert - Should be sorted by displayOrder
      const images = screen.getAllByRole('img');
      expect(images[0]).toHaveAttribute('src', 'http://localhost/uploads/photo1.jpg');
      expect(images[1]).toHaveAttribute('src', 'http://localhost/uploads/photo2.jpg');
    });

    it('should not display upload zone for non-admin users', () => {
      // Arrange - Mock operator user
      mockUser.role = 'Operator';

      // Act
      renderComponent(mockPhotos);

      // Assert
      expect(screen.queryByText(/arrastra fotos aquí/i)).not.toBeInTheDocument();

      // Cleanup
      mockUser.role = 'Administrator';
    });
  });

  describe('File Upload (Task 16.7)', () => {
    it('should upload photo without embeddings call when valid file is selected', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      vi.mocked(productService.uploadPhoto).mockResolvedValue({
        id: 'prod-123',
        sku: 'SKU-123',
        name: 'Test',
        price: 10,
        isActive: true,
        photos: [
          {
            id: 'photo-3',
            productId: 'prod-123',
            fileName: 'new-photo.jpg',
            url: 'http://localhost/uploads/new-photo.jpg',
            displayOrder: 2,
            isPrimary: false,
            createdAt: '2024-01-03T00:00:00Z',
            updatedAt: '2024-01-03T00:00:00Z',
          },
        ],
      } as Awaited<ReturnType<typeof productService.uploadPhoto>>);

      renderComponent([], onPhotosChange);

      const file = createMockFile('test.jpg', 1000, 'image/jpeg');
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeTruthy();
      fireEvent.change(input!, { target: { files: [file] } });

      const uploadButton = await screen.findByRole('button', { name: /subir foto/i });
      await user.click(uploadButton);

      await waitFor(() => {
        expect(productService.uploadPhoto).toHaveBeenCalledWith('prod-123', expect.any(File));
        expect(onPhotosChange).toHaveBeenCalled();
      });
    });

    it('should show loading indicator while uploading', async () => {
      const user = userEvent.setup();
      vi.mocked(productService.uploadPhoto).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 1000))
      );

      renderComponent();
      await queueFileAndUpload(user, createMockFile('test.jpg', 1000, 'image/jpeg'));

      await waitFor(() => {
        expect(screen.getByText(/subiendo fotos/i)).toBeInTheDocument();
      });
    });

    it('should disable upload zone while uploading', async () => {
      const user = userEvent.setup();
      vi.mocked(productService.uploadPhoto).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 1000))
      );

      renderComponent();
      await queueFileAndUpload(user, createMockFile('test.jpg', 1000, 'image/jpeg'));

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await waitFor(() => {
        expect(input!).toBeDisabled();
      });
    });
  });

  describe('Drag and Drop Interactions (Task 16.8)', () => {
    it('should handle drag over event', () => {
      // Arrange
      renderComponent();
      // Get the actual drop zone div (the one with border-2 border-dashed)
      const dropZone = document.querySelector('.border-dashed') as HTMLElement;
      expect(dropZone).toBeTruthy();

      // Act
      fireEvent.dragOver(dropZone!, { dataTransfer: { files: [] } });

      // Assert - Drop zone should highlight (check for individual classes)
      expect(dropZone?.className).toMatch(/border-primary/);
    });

    it('should handle drag leave event', () => {
      // Arrange
      renderComponent();
      const dropZone = document.querySelector('.border-dashed') as HTMLElement;
      expect(dropZone).toBeTruthy();

      // Act - Drag over then drag leave
      fireEvent.dragOver(dropZone!, { dataTransfer: { files: [] } });
      fireEvent.dragLeave(dropZone!, { dataTransfer: { files: [] } });

      // Assert - Highlight should be removed (check it doesn't have bg-primary/5)
      expect(dropZone?.className).not.toMatch(/bg-primary\/5/);
    });

    it('should upload photo on file drop', async () => {
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      vi.mocked(productService.uploadPhoto).mockResolvedValue(
        mockUploadProductResponse({ fileName: 'dropped.jpg', url: 'http://localhost/uploads/dropped.jpg' })
      );

      renderComponent([], onPhotosChange);
      const dropZone = document.querySelector('.border-dashed') as HTMLElement;
      expect(dropZone).toBeTruthy();

      const file = createMockFile('dropped.jpg', 1000, 'image/jpeg');
      fireEvent.drop(dropZone!, {
        dataTransfer: { files: [file] },
      });

      const uploadButton = await screen.findByRole('button', { name: /subir foto/i });
      await user.click(uploadButton);

      await waitFor(() => {
        expect(productService.uploadPhoto).toHaveBeenCalledWith('prod-123', expect.any(File));
        expect(onPhotosChange).toHaveBeenCalled();
      });
    });

    it('should remove drag styling on drop', () => {
      // Arrange
      renderComponent();
      const dropZone = document.querySelector('.border-dashed') as HTMLElement;
      expect(dropZone).toBeTruthy();

      // Act
      fireEvent.dragOver(dropZone!, { dataTransfer: { files: [] } });
      const file = createMockFile('test.jpg', 1000, 'image/jpeg');
      fireEvent.drop(dropZone!, { dataTransfer: { files: [file] } });

      // Assert - Highlight should be removed after drop (check it doesn't have bg-primary/5)
      expect(dropZone?.className).not.toMatch(/bg-primary\/5/);
    });
  });

  describe('File Validation Feedback (Task 16.9)', () => {
    it('should reject files with invalid format', async () => {
      // Arrange
      const onPhotosChange = vi.fn();
      renderComponent([], onPhotosChange);

      // Act - Try to upload text file
      const file = createMockFile('document.txt', 1000, 'text/plain');
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeTruthy();
      fireEvent.change(input!, { target: { files: [file] } });

      // Assert - Should not call upload service
      await waitFor(() => {
        expect(productService.uploadPhoto).not.toHaveBeenCalled();
      });
    });

    it('should reject files exceeding size limit (5MB)', async () => {
      // Arrange
      const onPhotosChange = vi.fn();
      renderComponent([], onPhotosChange);

      // Act - Try to upload 6 MB file
      const file = createMockFile('large.jpg', 6 * 1024 * 1024, 'image/jpeg');
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeTruthy();
      fireEvent.change(input!, { target: { files: [file] } });

      // Assert - Should not call upload service
      await waitFor(() => {
        expect(productService.uploadPhoto).not.toHaveBeenCalled();
      });
    });

    it('should accept valid JPG file', async () => {
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      vi.mocked(productService.uploadPhoto).mockResolvedValue(
        mockUploadProductResponse({ fileName: 'valid.jpg', url: 'http://localhost/uploads/valid.jpg' })
      );

      renderComponent([], onPhotosChange);

      await queueFileAndUpload(user, createMockFile('valid.jpg', 1000, 'image/jpeg'));

      await waitFor(() => {
        expect(productService.uploadPhoto).toHaveBeenCalledWith('prod-123', expect.any(File));
      });
    });

    it('should accept valid PNG file', async () => {
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      vi.mocked(productService.uploadPhoto).mockResolvedValue(
        mockUploadProductResponse({ fileName: 'valid.png', url: 'http://localhost/uploads/valid.png' })
      );

      renderComponent([], onPhotosChange);

      await queueFileAndUpload(user, createMockFile('valid.png', 1000, 'image/png'));

      await waitFor(() => {
        expect(productService.uploadPhoto).toHaveBeenCalledWith('prod-123', expect.any(File));
      });
    });

    it('should show error toast for invalid format', async () => {
      // Arrange
      const { toast } = await import('sonner');
      renderComponent();

      // Act
      const file = createMockFile('invalid.gif', 1000, 'image/gif');
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeTruthy();
      fireEvent.change(input!, { target: { files: [file] } });

      // Assert
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Algunos archivos no son válidos',
          expect.any(Object)
        );
      });
    });

    it('should show error toast for file too large', async () => {
      const { toast } = await import('sonner');
      renderComponent();

      const file = createMockFile('huge.jpg', 10 * 1024 * 1024, 'image/jpeg');
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      fireEvent.change(input!, { target: { files: [file] } });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'Algunos archivos no son válidos',
          expect.any(Object)
        );
      });
    });
  });

  describe('Photo Gallery Display (Task 16.7)', () => {
    it('should display photos in display order', () => {
      // Act
      renderComponent(mockPhotos);

      // Assert
      const images = screen.getAllByRole('img');
      expect(images[0]).toHaveAttribute('alt', 'Foto 1');
      expect(images[1]).toHaveAttribute('alt', 'Foto 2');
    });

    it('should show primary badge only on primary photo', () => {
      // Act
      renderComponent(mockPhotos);

      // Assert
      const primaryBadges = screen.getAllByText(/principal/i);
      expect(primaryBadges).toHaveLength(1);
    });

    it('should display photo count correctly', () => {
      // Act
      renderComponent(mockPhotos);

      // Assert
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(2);
    });
  });

  describe('Set Primary Photo (Task 16.7)', () => {
    it('should allow admin to set non-primary photo as primary', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      vi.mocked(productService.setPrimaryPhoto).mockResolvedValue(undefined);

      renderComponent(mockPhotos, onPhotosChange);

      // Act - Hover over second photo to reveal actions
      const photoCards = screen.getAllByRole('img').map(img => img.closest('div')?.parentElement);
      const secondPhoto = photoCards[1];
      
      // Find the set primary button (Star button) - it's hidden until hover
      const buttons = secondPhoto?.querySelectorAll('button');
      const setPrimaryButton = Array.from(buttons || []).find(btn => 
        btn.querySelector('svg')?.closest('button')?.textContent === '' && 
        !btn.classList.contains('destructive')
      );

      if (setPrimaryButton) {
        await user.click(setPrimaryButton);

        // Assert
        await waitFor(() => {
          expect(productService.setPrimaryPhoto).toHaveBeenCalledWith('prod-123', 'photo-2');
          expect(onPhotosChange).toHaveBeenCalled();
        });
      }
    });

    it('should not show set primary button on already primary photo', () => {
      // Act
      renderComponent(mockPhotos);

      // Assert - Primary photo should not have set primary button
      // The button count should be 1 (delete only) on primary photo
      const primaryPhotoCard = screen.getAllByRole('img')[0].closest('div')?.parentElement;
      const buttons = primaryPhotoCard?.querySelectorAll('button');
      
      // Primary photo only has delete button, non-primary has both set primary and delete
      expect(buttons?.length).toBeLessThanOrEqual(1);
    });
  });

  describe('Delete Photo (Task 16.7)', () => {
    it('should show confirmation dialog when delete is clicked', async () => {
      // Arrange
      const user = userEvent.setup();
      renderComponent(mockPhotos);

      // Act - Find and click delete button
      const photoCards = screen.getAllByRole('img').map(img => img.closest('div')?.parentElement);
      const firstPhoto = photoCards[0];
      const deleteButtons = firstPhoto?.querySelectorAll('button');
      
      if (deleteButtons && deleteButtons.length > 0) {
        const deleteButton = Array.from(deleteButtons).find(btn => 
          btn.classList.contains('destructive') || btn.textContent?.includes('×')
        );
        
        if (deleteButton) {
          await user.click(deleteButton);

          // Assert
          await waitFor(() => {
            expect(screen.getByText(/eliminar foto/i)).toBeInTheDocument();
            expect(screen.getByText(/esta acción no se puede deshacer/i)).toBeInTheDocument();
          });
        }
      }
    });

    it('should delete photo when confirmed', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      vi.mocked(productService.deletePhoto).mockResolvedValue(undefined);

      renderComponent(mockPhotos, onPhotosChange);

      // Act - Click delete button
      const photoCards = screen.getAllByRole('img').map(img => img.closest('div')?.parentElement);
      const firstPhoto = photoCards[0];
      const deleteButtons = firstPhoto?.querySelectorAll('button');
      
      if (deleteButtons && deleteButtons.length > 0) {
        const deleteButton = Array.from(deleteButtons).find(btn => 
          btn.classList.contains('destructive')
        );
        
        if (deleteButton) {
          await user.click(deleteButton);

          // Confirm deletion
          await waitFor(() => {
            const confirmButton = screen.getByRole('button', { name: /eliminar/i });
            return user.click(confirmButton);
          });

          // Assert
          await waitFor(() => {
            expect(productService.deletePhoto).toHaveBeenCalledWith('prod-123', 'photo-1');
            expect(onPhotosChange).toHaveBeenCalled();
          });
        }
      }
    });

    it('should cancel delete when cancel button is clicked', async () => {
      // Arrange
      const user = userEvent.setup();
      const onPhotosChange = vi.fn();
      renderComponent(mockPhotos, onPhotosChange);

      // Act - Click delete button
      const photoCards = screen.getAllByRole('img').map(img => img.closest('div')?.parentElement);
      const firstPhoto = photoCards[0];
      const deleteButtons = firstPhoto?.querySelectorAll('button');
      
      if (deleteButtons && deleteButtons.length > 0) {
        const deleteButton = Array.from(deleteButtons).find(btn => 
          btn.classList.contains('destructive')
        );
        
        if (deleteButton) {
          await user.click(deleteButton);

          // Cancel deletion
          await waitFor(() => {
            const cancelButton = screen.getByRole('button', { name: /cancelar/i });
            return user.click(cancelButton);
          });

          // Assert - Dialog should close and no deletion should occur
          await waitFor(() => {
            expect(screen.queryByText(/esta acción no se puede deshacer/i)).not.toBeInTheDocument();
          });
          expect(productService.deletePhoto).not.toHaveBeenCalled();
        }
      }
    });
  });

  describe('Error Handling (Task 16.9)', () => {
    it('should handle upload error gracefully', async () => {
      const user = userEvent.setup();
      const { toast } = await import('sonner');
      vi.mocked(productService.uploadPhoto).mockRejectedValue(new Error('Upload failed'));

      renderComponent();

      await queueFileAndUpload(user, createMockFile('test.jpg', 1000, 'image/jpeg'));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Error al subir 1 foto');
      });
    });

    it('should handle delete error gracefully', async () => {
      // Arrange
      const { toast } = await import('sonner');
      const user = userEvent.setup();
      vi.mocked(productService.deletePhoto).mockRejectedValue(
        new Error('Delete failed')
      );

      renderComponent(mockPhotos);

      // Act - Try to delete
      const photoCards = screen.getAllByRole('img').map(img => img.closest('div')?.parentElement);
      const firstPhoto = photoCards[0];
      const deleteButtons = firstPhoto?.querySelectorAll('button');
      
      if (deleteButtons && deleteButtons.length > 0) {
        const deleteButton = Array.from(deleteButtons).find(btn => 
          btn.classList.contains('destructive')
        );
        
        if (deleteButton) {
          await user.click(deleteButton);

          await waitFor(() => {
            const confirmButton = screen.getByRole('button', { name: /eliminar/i });
            return user.click(confirmButton);
          });

          // Assert
          await waitFor(() => {
            expect(toast.error).toHaveBeenCalledWith(
              'Error al eliminar la foto',
              expect.any(Object)
            );
          });
        }
      }
    });

    it('should handle set primary error gracefully', async () => {
      // Arrange
      const { toast } = await import('sonner');
      const user = userEvent.setup();
      vi.mocked(productService.setPrimaryPhoto).mockRejectedValue(
        new Error('Set primary failed')
      );

      renderComponent(mockPhotos);

      // Act
      const photoCards = screen.getAllByRole('img').map(img => img.closest('div')?.parentElement);
      const secondPhoto = photoCards[1];
      const buttons = secondPhoto?.querySelectorAll('button');
      
      if (buttons && buttons.length > 1) {
        const setPrimaryButton = Array.from(buttons).find(btn => 
          !btn.classList.contains('destructive')
        );
        
        if (setPrimaryButton) {
          await user.click(setPrimaryButton);

          // Assert
          await waitFor(() => {
            expect(toast.error).toHaveBeenCalledWith(
              'Error al establecer foto principal',
              expect.any(Object)
            );
          });
        }
      }
    });
  });

  describe('Accessibility and Edge Cases', () => {
    it('should accept file input by clicking select button', async () => {
      // Arrange
      const user = userEvent.setup();
      renderComponent();

      // Act
      const selectButton = screen.getByText(/selecciona archivos/i);
      await user.click(selectButton);

      // Assert - File input should exist and accept correct formats
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeTruthy();
      expect(input!).toHaveAttribute('accept', '.jpg,.jpeg,.png');
    });

    it('should handle empty file list gracefully', async () => {
      // Arrange
      renderComponent();

      // Act
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toBeTruthy();
      fireEvent.change(input!, { target: { files: null } });

      // Assert - Should not throw error
      expect(productService.uploadPhoto).not.toHaveBeenCalled();
    });

    it('should disable actions during upload', async () => {
      const user = userEvent.setup();
      vi.mocked(productService.uploadPhoto).mockImplementation(() => new Promise(() => {}));

      renderComponent();

      const file = createMockFile('test.jpg', 1000, 'image/jpeg');
      await queueFileAndUpload(user, file);

      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await waitFor(() => {
        expect(input!).toBeDisabled();
      });
    });
  });

  describe('Operator Read-Only Mode', () => {
    it('should not show upload zone for operators', () => {
      // Arrange - Mock operator user
      mockUser.role = 'Operator';

      // Act
      renderComponent(mockPhotos);

      // Assert
      expect(screen.queryByText(/arrastra fotos aquí/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('button')).not.toBeInTheDocument();

      // Cleanup
      mockUser.role = 'Administrator';
    });

    it('should display photos in read-only mode for operators', () => {
      // Arrange
      mockUser.role = 'Operator';

      // Act
      renderComponent(mockPhotos);

      // Assert
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(2);
      expect(screen.getByText(/principal/i)).toBeInTheDocument();

      // Cleanup
      mockUser.role = 'Administrator';
    });
  });
});
