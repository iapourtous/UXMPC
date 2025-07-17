import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { llmApi } from '../services/api';
import { normalizeMongoData } from '../utils/normalizeData';

export const useLLMProfiles = (activeOnly = false) => {
  return useQuery({
    queryKey: ['llmProfiles', activeOnly],
    queryFn: async () => {
      const response = await llmApi.list(activeOnly);
      return normalizeMongoData(response.data);
    },
  });
};

export const useLLMProfile = (id) => {
  return useQuery({
    queryKey: ['llmProfile', id],
    queryFn: async () => {
      const response = await llmApi.get(id);
      return normalizeMongoData(response.data);
    },
    enabled: !!id,
  });
};

export const useCreateLLMProfile = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data) => {
      const response = await llmApi.create(data);
      return normalizeMongoData(response.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmProfiles'] });
    },
  });
};

export const useUpdateLLMProfile = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, data }) => {
      const response = await llmApi.update(id, data);
      return normalizeMongoData(response.data);
    },
    onSuccess: (data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['llmProfiles'] });
      queryClient.invalidateQueries({ queryKey: ['llmProfile', id] });
    },
  });
};

export const useDeleteLLMProfile = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id) => {
      const response = await llmApi.delete(id);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llmProfiles'] });
    },
  });
};