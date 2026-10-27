import { AppRouting } from '@/routing/app-routing';
import { ThemeProvider } from 'next-themes';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { AuthProvider } from '@/providers';
import { CartProvider } from '@/providers/cart-provider';
const { BASE_URL } = import.meta.env;

export function App() {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      storageKey="vite-theme"
      enableSystem
      disableTransitionOnChange
      enableColorScheme
    >
      <BrowserRouter basename={BASE_URL}>
        <AuthProvider>
          <CartProvider>
            <Toaster />
            <AppRouting />
          </CartProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
