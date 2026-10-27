/**
 * Product Photo Upload Component - EP1 HU-EP1-004
 * Component for uploading and managing product photos
 * Admin-only: Upload, delete, and set primary photo
 * Operator: Read-only view of photos
 * 
 * Supports multiple file upload with progress tracking
 */

import { useState, useRef, useCallback } from 'react';
import { Upload, X, Star, Loader2, Image as ImageIcon, CheckCircle2, AlertCircle, FileImage } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useAuth } from '@/providers/auth-provider';
import { productService } from '@/services/product.service';
import { ProductPhoto } from '@/types/product.types';
import { getImageUrl } from '@/lib/image-url';

interface ProductPhotoUploadProps {
  productId: string;
  productSku: string;
  photos: ProductPhoto[];
  onPhotosChange: () => void;
}

// Representa un archivo pendiente de subir
interface PendingFile {
  id: string;
  file: File;
  previewUrl: string;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
}

export function ProductPhotoUpload({ productId, photos, onPhotosChange }: ProductPhotoUploadProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrator';
  
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [photoToDelete, setPhotoToDelete] = useState<string | null>(null);
  const [deletingPhotoId, setDeletingPhotoId] = useState<string | null>(null);
  const [settingPrimaryPhotoId, setSettingPrimaryPhotoId] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const allowedFormats = ['image/jpeg', 'image/jpg', 'image/png'];
  const maxFileSize = 5 * 1024 * 1024; // 5 MB

  const validateFile = (file: File): string | null => {
    if (!allowedFormats.includes(file.type)) {
      return 'Solo se permiten archivos JPG y PNG';
    }
    if (file.size > maxFileSize) {
      return 'El archivo no puede superar 5 MB';
    }
    return null;
  };

  // Crear un ID único para cada archivo
  const generateFileId = () => `file-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

  // Añadir archivos a la cola pendiente
  const addFilesToQueue = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;

    const newPendingFiles: PendingFile[] = [];
    const errors: string[] = [];

    Array.from(files).forEach((file) => {
      const error = validateFile(file);
      if (error) {
        errors.push(`${file.name}: ${error}`);
      } else {
        newPendingFiles.push({
          id: generateFileId(),
          file,
          previewUrl: URL.createObjectURL(file),
          status: 'pending',
        });
      }
    });

    if (errors.length > 0) {
      toast.error('Algunos archivos no son válidos', {
        description: errors.slice(0, 3).join('\n') + (errors.length > 3 ? `\n... y ${errors.length - 3} más` : ''),
      });
    }

    if (newPendingFiles.length > 0) {
      setPendingFiles((prev) => [...prev, ...newPendingFiles]);
    }
  }, []);

  // Remover archivo de la cola
  const removeFromQueue = useCallback((fileId: string) => {
    setPendingFiles((prev) => {
      const file = prev.find((f) => f.id === fileId);
      if (file) {
        URL.revokeObjectURL(file.previewUrl);
      }
      return prev.filter((f) => f.id !== fileId);
    });
  }, []);

  // Subir todos los archivos pendientes
  const uploadAllPhotos = useCallback(async () => {
    const filesToUpload = pendingFiles.filter((f) => f.status === 'pending');
    if (filesToUpload.length === 0) return;

    setIsUploading(true);
    setUploadProgress({ current: 0, total: filesToUpload.length });

    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < filesToUpload.length; i++) {
      const pendingFile = filesToUpload[i];
      
      // Marcar como subiendo
      setPendingFiles((prev) =>
        prev.map((f) => (f.id === pendingFile.id ? { ...f, status: 'uploading' as const } : f))
      );

      try {
        await productService.uploadPhoto(productId, pendingFile.file);
        successCount++;

        // Marcar como éxito y remover después de un breve delay
        setPendingFiles((prev) =>
          prev.map((f) => (f.id === pendingFile.id ? { ...f, status: 'success' as const } : f))
        );
        
        // Limpiar el archivo exitoso después de mostrar el estado
        setTimeout(() => {
          setPendingFiles((prev) => {
            const file = prev.find((f) => f.id === pendingFile.id);
            if (file) {
              URL.revokeObjectURL(file.previewUrl);
            }
            return prev.filter((f) => f.id !== pendingFile.id);
          });
        }, 1500);
        
      } catch (error: any) {
        console.error('Failed to upload photo:', error);
        errorCount++;
        const errorMessage = error.response?.data?.error || 'Error al subir';
        
        setPendingFiles((prev) =>
          prev.map((f) => (f.id === pendingFile.id ? { ...f, status: 'error' as const, error: errorMessage } : f))
        );
      }

      setUploadProgress({ current: i + 1, total: filesToUpload.length });
    }

    setIsUploading(false);
    onPhotosChange();

    // Mostrar resumen
    if (successCount > 0 && errorCount === 0) {
      toast.success(`${successCount} foto${successCount > 1 ? 's' : ''} subida${successCount > 1 ? 's' : ''} exitosamente`);
    } else if (successCount > 0 && errorCount > 0) {
      toast.warning(`${successCount} foto${successCount > 1 ? 's' : ''} subida${successCount > 1 ? 's' : ''}, ${errorCount} con error`);
    } else if (errorCount > 0) {
      toast.error(`Error al subir ${errorCount} foto${errorCount > 1 ? 's' : ''}`);
    }

    // Clear file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [pendingFiles, productId, onPhotosChange]);

  const handleFileSelect = async (files: FileList | null) => {
    addFilesToQueue(files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleSetPrimary = async (photoId: string) => {
    if (!isAdmin) return;
    
    setSettingPrimaryPhotoId(photoId);
    try {
      await productService.setPrimaryPhoto(productId, photoId);
      toast.success('Foto principal actualizada');
      onPhotosChange();
    } catch (error: any) {
      console.error('Failed to set primary photo:', error);
      const errorMessage = error.response?.data?.error || 'Error al establecer foto principal';
      toast.error('Error al establecer foto principal', { description: errorMessage });
    } finally {
      setSettingPrimaryPhotoId(null);
    }
  };

  const handleDeleteClick = (photoId: string) => {
    if (!isAdmin) return;
    setPhotoToDelete(photoId);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!photoToDelete) return;

    setDeletingPhotoId(photoToDelete);
    setDeleteConfirmOpen(false);
    
    const deletedPhotoId = photoToDelete;

    try {
      await productService.deletePhoto(productId, deletedPhotoId);
      toast.success('Foto eliminada');
      onPhotosChange();
    } catch (error: any) {
      console.error('Failed to delete photo:', error);
      const errorMessage = error.response?.data?.error || 'Error al eliminar la foto';
      toast.error('Error al eliminar la foto', { description: errorMessage });
    } finally {
      setDeletingPhotoId(null);
      setPhotoToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmOpen(false);
    setPhotoToDelete(null);
  };

  const sortedPhotos = [...photos].sort((a, b) => a.displayOrder - b.displayOrder);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Fotos del Producto</CardTitle>
        <CardDescription>
          Sube fotos del catálogo. Formatos: JPG, PNG (máx. 5 MB)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Upload Zone - Admin Only */}
        {isAdmin && (
          <div className="space-y-4">
            {/* Dropzone */}
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 ${
                isDragging
                  ? 'border-primary bg-primary/10 scale-[1.02]'
                  : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30'
              } ${isUploading ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !isUploading && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png"
                multiple
                onChange={(e) => handleFileSelect(e.target.files)}
                className="hidden"
                disabled={isUploading}
              />

              <div className="flex flex-col items-center gap-3">
                <div className={`rounded-full p-4 transition-colors ${isDragging ? 'bg-primary/20' : 'bg-muted'}`}>
                  <Upload className={`size-8 transition-colors ${isDragging ? 'text-primary' : 'text-muted-foreground'}`} />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium">
                    Arrastra fotos aquí o{' '}
                    <span className="text-primary hover:underline">
                      selecciona archivos
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    JPG, PNG hasta 5 MB • Puedes seleccionar múltiples archivos
                  </p>
                </div>
              </div>
            </div>

            {/* Pending Files Preview */}
            {pendingFiles.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium flex items-center gap-2">
                    <FileImage className="size-4" />
                    Archivos pendientes ({pendingFiles.length})
                  </h4>
                  {!isUploading && (
                    <Button
                      size="sm"
                      onClick={uploadAllPhotos}
                      disabled={pendingFiles.filter((f) => f.status === 'pending').length === 0}
                    >
                      <Upload className="size-4 mr-2" />
                      Subir {pendingFiles.filter((f) => f.status === 'pending').length > 1 
                        ? `${pendingFiles.filter((f) => f.status === 'pending').length} fotos`
                        : 'foto'}
                    </Button>
                  )}
                </div>

                {/* Upload Progress Bar */}
                {isUploading && uploadProgress.total > 0 && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Subiendo fotos...</span>
                      <span>{uploadProgress.current} de {uploadProgress.total}</span>
                    </div>
                    <Progress 
                      value={(uploadProgress.current / uploadProgress.total) * 100} 
                      className="h-2"
                    />
                  </div>
                )}

                {/* File Grid Preview */}
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                  {pendingFiles.map((pendingFile) => (
                    <div
                      key={pendingFile.id}
                      className="relative group aspect-square rounded-lg overflow-hidden border bg-muted"
                    >
                      <img
                        src={pendingFile.previewUrl}
                        alt={pendingFile.file.name}
                        className={`w-full h-full object-cover transition-opacity ${
                          pendingFile.status === 'uploading' ? 'opacity-50' : ''
                        }`}
                      />
                      
                      {/* Status Overlay */}
                      {pendingFile.status === 'uploading' && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                          <Loader2 className="size-6 animate-spin text-white" />
                        </div>
                      )}
                      
                      {pendingFile.status === 'success' && (
                        <div className="absolute inset-0 flex items-center justify-center bg-green-500/40">
                          <CheckCircle2 className="size-6 text-white" />
                        </div>
                      )}
                      
                      {pendingFile.status === 'error' && (
                        <div className="absolute inset-0 flex items-center justify-center bg-red-500/40">
                          <AlertCircle className="size-6 text-white" />
                        </div>
                      )}

                      {/* Remove Button - only for pending files */}
                      {pendingFile.status === 'pending' && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeFromQueue(pendingFile.id);
                          }}
                          className="absolute top-1 right-1 p-1 rounded-full bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/80"
                        >
                          <X className="size-3" />
                        </button>
                      )}

                      {/* File name tooltip */}
                      <div className="absolute bottom-0 inset-x-0 p-1 bg-gradient-to-t from-black/60 to-transparent">
                        <p className="text-[10px] text-white truncate px-1" title={pendingFile.file.name}>
                          {pendingFile.file.name}
                        </p>
                      </div>

                      {/* Error message */}
                      {pendingFile.error && (
                        <div className="absolute inset-x-0 bottom-0 p-2 bg-red-500/90">
                          <p className="text-[10px] text-white text-center">{pendingFile.error}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Clear all button */}
                {!isUploading && pendingFiles.length > 1 && (
                  <div className="flex justify-end">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        pendingFiles.forEach((f) => URL.revokeObjectURL(f.previewUrl));
                        setPendingFiles([]);
                      }}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <X className="size-3 mr-1" />
                      Limpiar cola
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Photo Gallery */}
        {sortedPhotos.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {sortedPhotos.map((photo) => (
              <div key={photo.id} className="relative group">
                <div className="aspect-square rounded-lg overflow-hidden border bg-muted">
                  {photo.url ? (
                    <img
                      src={getImageUrl(photo.url)}
                      alt={`Foto ${photo.displayOrder + 1}`}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <ImageIcon className="size-8 text-muted-foreground" />
                    </div>
                  )}
                </div>

                {/* Primary Badge */}
                {photo.isPrimary && (
                  <Badge className="absolute top-2 left-2 gap-1">
                    <Star className="size-3 fill-current" />
                    Principal
                  </Badge>
                )}

                {/* Actions - Admin Only */}
                {isAdmin && (
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                    {!photo.isPrimary && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleSetPrimary(photo.id)}
                        disabled={settingPrimaryPhotoId === photo.id || deletingPhotoId === photo.id}
                      >
                        {settingPrimaryPhotoId === photo.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Star className="size-4" />
                        )}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDeleteClick(photo.id)}
                      disabled={deletingPhotoId === photo.id || settingPrimaryPhotoId === photo.id}
                    >
                      {deletingPhotoId === photo.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <X className="size-4" />
                      )}
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <ImageIcon className="size-12 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No hay fotos subidas aún</p>
            <p className="text-xs">Sube la primera foto para comenzar</p>
          </div>
        )}

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Eliminar foto</DialogTitle>
              <DialogDescription>
                ¿Estás seguro de que deseas eliminar esta foto? Esta acción no se puede deshacer.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={handleDeleteCancel}>
                Cancelar
              </Button>
              <Button variant="destructive" onClick={handleDeleteConfirm}>
                Eliminar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

