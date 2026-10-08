import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { Business, InvoicePatch, NewInvoiceInput } from './types';

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: api.me, staleTime: 60_000 });

export const useInvoices = () =>
  useQuery({ queryKey: ['invoices'], queryFn: api.listInvoices, refetchInterval: 30_000 });

export const useInvoice = (id: string) =>
  useQuery({ queryKey: ['invoice', id], queryFn: () => api.getInvoice(id), refetchInterval: 30_000 });

export const useEvents = (id: string) =>
  useQuery({ queryKey: ['events', id], queryFn: () => api.events(id), refetchInterval: 30_000 });

export const useDebtor = (key?: string | null, enabled = true) =>
  useQuery({
    queryKey: ['debtor', key],
    queryFn: () => api.debtor(key as string),
    enabled: enabled && !!key,
    staleTime: 10 * 60_000,
  });

function useRefresh() {
  const qc = useQueryClient();
  return (id?: string) => {
    qc.invalidateQueries({ queryKey: ['invoices'] });
    if (id) {
      qc.invalidateQueries({ queryKey: ['invoice', id] });
      qc.invalidateQueries({ queryKey: ['events', id] });
    }
  };
}

export function usePatchInvoice(id: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (p: InvoicePatch) => api.patchInvoice(id, p), onSuccess: () => refresh(id) });
}

export function useChase(id: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (body?: string) => api.chase(id, body), onSuccess: () => refresh(id) });
}

export function useSendLba(id: string) {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (body?: string) => api.sendLba(id, body), onSuccess: () => refresh(id) });
}

export function useCreateInvoice() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (i: NewInvoiceInput) => api.createInvoice(i), onSuccess: () => refresh() });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: Partial<Business>) => api.updateMe(p),
    onSuccess: (me) => qc.setQueryData(['me'], me),
  });
}
