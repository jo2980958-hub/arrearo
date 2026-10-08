import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './auth/AuthContext';
import { ToastProvider } from './components/ui';
import Shell from './components/Shell';
import Login from './pages/Login';
import Onboarding from './pages/Onboarding';
import Overview from './pages/Overview';
import Invoices from './pages/Invoices';
import InvoiceDetail from './pages/InvoiceDetail';
import AddInvoice from './pages/AddInvoice';
import Settings from './pages/Settings';
import { ApiError } from './api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          {/* HashRouter: deep links work on S3/CloudFront without rewrite rules. */}
          <HashRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/onboarding" element={<Onboarding />} />
              <Route element={<Shell />}>
                <Route index element={<Overview />} />
                <Route path="invoices" element={<Invoices />} />
                <Route path="invoices/new" element={<AddInvoice />} />
                <Route path="invoices/:id" element={<InvoiceDetail />} />
                <Route path="settings" element={<Settings />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </HashRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
