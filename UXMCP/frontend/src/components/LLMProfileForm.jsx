import React, { useState, useEffect } from 'react';
import { useCreateLLMProfile, useUpdateLLMProfile } from '../hooks/useLLMProfiles';

export default function LLMProfileForm({ profile, onClose }) {
  const createMutation = useCreateLLMProfile();
  const updateMutation = useUpdateLLMProfile();
  
  const [formData, setFormData] = useState({
    name: '',
    model: '',
    endpoint: '',
    api_key: '',
    max_tokens: 4096,
    temperature: 0.7,
    mode: 'json',
    system_prompt: '',
    description: '',
    active: true,
  });

  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    if (profile) {
      setFormData({
        name: profile.name || '',
        model: profile.model || '',
        endpoint: profile.endpoint || '',
        api_key: profile.api_key || '',
        max_tokens: profile.max_tokens || 4096,
        temperature: profile.temperature || 0.7,
        mode: profile.mode || 'json',
        system_prompt: profile.system_prompt || '',
        description: profile.description || '',
        active: profile.active !== undefined ? profile.active : true,
      });
    }
  }, [profile]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // Convert numeric fields to numbers
      const submitData = {
        ...formData,
        max_tokens: parseInt(formData.max_tokens),
        temperature: parseFloat(formData.temperature)
      };
      
      if (profile) {
        await updateMutation.mutateAsync({ id: profile.id, data: submitData });
      } else {
        await createMutation.mutateAsync(submitData);
      }
      onClose();
    } catch (error) {
      console.error('Failed to save LLM profile:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
        <h3 className="text-lg font-bold text-gray-900 mb-4">
          {profile ? 'Edit LLM Profile' : 'Create New LLM Profile'}
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              placeholder="openai-gpt-4o"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Model Name</label>
            <input
              type="text"
              name="model"
              value={formData.model}
              onChange={handleChange}
              required
              placeholder="gpt-4o, claude-3-sonnet, llama-3-8b, etc."
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              Enter the exact model name as required by your provider
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Endpoint URL (Optional)</label>
            <input
              type="url"
              name="endpoint"
              value={formData.endpoint}
              onChange={handleChange}
              placeholder="https://api.openai.com/v1, https://api.anthropic.com, etc."
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              Leave empty to use default provider endpoint
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">System Prompt</label>
            <textarea
              name="system_prompt"
              value={formData.system_prompt}
              onChange={handleChange}
              rows={4}
              placeholder="You are a helpful assistant that..."
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              Define the assistant's behavior and personality
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows={3}
              placeholder="Describe recommended use cases, capabilities, or special configurations..."
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Mode</label>
              <select
                name="mode"
                value={formData.mode}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="json">JSON</option>
                <option value="text">Text</option>
                <option value="markdown">Markdown</option>
              </select>
            </div>
            <div></div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">API Key</label>
            <div className="mt-1 relative">
              <input
                type={showApiKey ? "text" : "password"}
                name="api_key"
                value={formData.api_key}
                onChange={handleChange}
                required
                placeholder="sk-..."
                className="block w-full pr-10 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm leading-5"
              >
                {showApiKey ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Max Tokens</label>
              <input
                type="number"
                name="max_tokens"
                value={formData.max_tokens}
                onChange={handleChange}
                min="1"
                max="128000"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Temperature</label>
              <input
                type="number"
                name="temperature"
                value={formData.temperature}
                onChange={handleChange}
                min="0"
                max="2"
                step="0.1"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              name="active"
              checked={formData.active}
              onChange={handleChange}
              className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            />
            <label htmlFor="active" className="ml-2 block text-sm text-gray-900">
              Active
            </label>
          </div>

          <div className="flex justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-300 text-black rounded hover:bg-gray-400"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isLoading || updateMutation.isLoading}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            >
              {createMutation.isLoading || updateMutation.isLoading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}