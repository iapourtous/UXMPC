import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { servicesApi } from '../services/api';
import { normalizeMongoData } from '../utils/normalizeData';

export const useServices = (activeOnly = false) => {
  return useQuery({
    queryKey: ['services', activeOnly],
    queryFn: async () => {
      const response = await servicesApi.list(activeOnly);
      return normalizeMongoData(response.data);
    },
  });
};

export const useService = (id) => {
  return useQuery({
    queryKey: ['service', id],
    queryFn: async () => {
      const response = await servicesApi.get(id);
      return normalizeMongoData(response.data);
    },
    enabled: !!id,
  });
};

export const useCreateService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data) => {
      const response = await servicesApi.create(data);
      return normalizeMongoData(response.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
    },
  });
};

export const useUpdateService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, data }) => {
      const response = await servicesApi.update(id, data);
      return normalizeMongoData(response.data);
    },
    onSuccess: (data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      queryClient.invalidateQueries({ queryKey: ['service', id] });
    },
  });
};

export const useDeleteService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: servicesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
    },
  });
};

export const useActivateService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id) => {
      const response = await servicesApi.activate(id);
      return normalizeMongoData(response.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
    },
  });
};

export const useDeactivateService = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id) => {
      const response = await servicesApi.deactivate(id);
      return normalizeMongoData(response.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
    },
  });
};