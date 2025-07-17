import React, { useState, useEffect } from 'react';
import { useCreateService, useUpdateService } from '../hooks/useServices';
import { useLLMProfiles } from '../hooks/useLLMProfiles';

const defaultCodes = {
  tool: `def handler(**params):
    # Your tool logic here
    return {"result": "Hello from dynamic tool!"}`,
  resource: `def handler(**params):
    # Your resource logic here
    # Return the content that should be exposed as a resource
    return {"content": "This is my dynamic resource content"}`,
  prompt: `def handler(**params):
    # Your prompt logic here
    # You can modify the template based on parameters
    template = params.get('template', '{greeting} {name}!')
    return {"template": template}`
};

export default function ServiceForm({ service, onClose }) {
  const createMutation = useCreateService();
  const updateMutation = useUpdateService();
  const { data: llmProfiles } = useLLMProfiles(true);
  
  const [isGenerating, setIsGenerating] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    service_type: 'tool',
    route: '',
    method: 'GET',
    description: '',
    code: defaultCodes.tool,
    dependencies: [],
    params: [],
    llm_profile: '',
    input_schema: null,
    output_schema: null,
    // Resource fields
    mime_type: 'text/plain',
    // Prompt fields
    prompt_template: '',
    prompt_args: [],
    documentation: '',
  });

  const [newParam, setNewParam] = useState({
    name: '',
    type: 'string',
    required: true,
    description: '',
  });

  useEffect(() => {
    if (service) {
      setFormData({
        name: service.name || '',
        service_type: service.service_type || 'tool',
        route: service.route || '',
        method: service.method || 'GET',
        description: service.description || '',
        code: service.code || defaultCodes[service.service_type || 'tool'],
        dependencies: service.dependencies || [],
        params: service.params || [],
        llm_profile: service.llm_profile || '',
        input_schema: service.input_schema || null,
        output_schema: service.output_schema || null,
        mime_type: service.mime_type || 'text/plain',
        prompt_template: service.prompt_template || '',
        prompt_args: service.prompt_args || [],
        documentation: service.documentation || '',
      });
    }
  }, [service]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    // If service type changes, update the default code
    if (name === 'service_type') {
      setFormData(prev => ({ 
        ...prev, 
        [name]: value,
        code: defaultCodes[value] || prev.code
      }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleDependenciesChange = (e) => {
    const deps = e.target.value.split(',').map(d => d.trim()).filter(d => d);
    setFormData(prev => ({ ...prev, dependencies: deps }));
  };

  const handleAddParam = () => {
    if (newParam.name) {
      setFormData(prev => ({
        ...prev,
        params: [...prev.params, { ...newParam }],
      }));
      setNewParam({ name: '', type: 'string', required: true, description: '' });
    }
  };

  const handleRemoveParam = (index) => {
    setFormData(prev => ({
      ...prev,
      params: prev.params.filter((_, i) => i !== index),
    }));
  };

  const handleAddPromptArg = () => {
    if (newParam.name) {
      setFormData(prev => ({
        ...prev,
        prompt_args: [...prev.prompt_args, { ...newParam }],
      }));
      setNewParam({ name: '', type: 'string', required: true, description: '' });
    }
  };

  const handleRemovePromptArg = (index) => {
    setFormData(prev => ({
      ...prev,
      prompt_args: prev.prompt_args.filter((_, i) => i !== index),
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (service) {
        await updateMutation.mutateAsync({ id: service.id, data: formData });
      } else {
        await createMutation.mutateAsync(formData);
      }
      onClose();
    } catch (error) {
      console.error('Failed to save service:', error);
    }
  };

  // Check if we can generate with AI
  const canGenerate = formData.name && 
                     formData.route && 
                     formData.llm_profile && 
                     formData.description &&
                     !service; // Only for new services

  const handleGenerate = async () => {
    try {
      setIsGenerating(true);
      
      const response = await fetch('http://localhost:8000/services/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          service_type: formData.service_type,
          route: formData.route,
          method: formData.method,
          description: formData.description,
          llm_profile: formData.llm_profile,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to generate service');
      }

      const generated = await response.json();
      
      // Update form with generated data
      setFormData(prev => ({
        ...prev,
        code: generated.code || prev.code,
        params: generated.params || prev.params,
        dependencies: generated.dependencies || prev.dependencies,
        documentation: generated.documentation || prev.documentation,
        output_schema: generated.output_schema || prev.output_schema,
        mime_type: generated.mime_type || prev.mime_type,
        prompt_template: generated.prompt_template || prev.prompt_template,
        prompt_args: generated.prompt_args || prev.prompt_args,
      }));
      
      alert('Service generated successfully! Review and adjust as needed.');
    } catch (error) {
      console.error('Failed to generate service:', error);
      alert('Failed to generate service: ' + error.message);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-4xl shadow-lg rounded-md bg-white">
        <h3 className="text-lg font-bold text-gray-900 mb-4">
          {service ? 'Edit Service' : 'Create New Service'}
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Service Type</label>
            <select
              name="service_type"
              value={formData.service_type}
              onChange={handleChange}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              <option value="tool">🔧 Tool - Execute actions and functions</option>
              <option value="resource">📄 Resource - Expose data and content</option>
              <option value="prompt">💬 Prompt - Provide reusable prompt templates</option>
            </select>
            <p className="mt-1 text-xs text-gray-500">
              {formData.service_type === 'tool' && 'Tools are functions that can be called by LLMs to perform actions.'}
              {formData.service_type === 'resource' && 'Resources expose data that can be read by LLMs for context.'}
              {formData.service_type === 'prompt' && 'Prompts are reusable templates for LLM interactions.'}
            </p>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700">Route</label>
              <input
                type="text"
                name="route"
                value={formData.route}
                onChange={handleChange}
                required
                placeholder="/api/myservice"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Method</label>
              <select
                name="method"
                value={formData.method}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">LLM Profile (Optional)</label>
              <select
                name="llm_profile"
                value={formData.llm_profile}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="">No LLM profile</option>
                {llmProfiles?.map((profile) => (
                  <option key={profile.id} value={profile.name}>
                    {profile.name} ({profile.model})
                  </option>
                ))}
              </select>
              {(!llmProfiles || llmProfiles.length === 0) && (
                <p className="mt-1 text-xs text-gray-500">
                  No active LLM profiles found. Create one in the LLM Profiles tab.
                </p>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <div className="mt-1 flex gap-2">
              <input
                type="text"
                name="description"
                value={formData.description}
                onChange={handleChange}
                className="flex-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
              {canGenerate && (
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="px-4 py-2 bg-purple-500 text-white rounded-md hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {isGenerating ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Generating...
                    </>
                  ) : (
                    <>
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      Generate with AI
                    </>
                  )}
                </button>
              )}
            </div>
            {canGenerate && (
              <p className="mt-1 text-xs text-purple-600">
                All required fields are filled. Click "Generate with AI" to auto-complete the service.
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Documentation (for LLM testing)</label>
            <textarea
              name="documentation"
              value={formData.documentation}
              onChange={handleChange}
              rows={4}
              placeholder="Detailed documentation for LLM to understand how to use and test this service. Include expected inputs, outputs, and behavior..."
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              This documentation will be used by the LLM to generate test cases and validate service behavior
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Dependencies (comma-separated)</label>
            <input
              type="text"
              value={formData.dependencies.join(', ')}
              onChange={handleDependenciesChange}
              placeholder="requests, json, datetime"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Parameters</label>
            <div className="space-y-2">
              {formData.params.map((param, index) => (
                <div key={index} className="flex items-center space-x-2 bg-gray-50 p-2 rounded">
                  <span className="text-sm">{param.name} ({param.type})</span>
                  <span className="text-xs text-gray-500">{param.required ? 'Required' : 'Optional'}</span>
                  {param.description && <span className="text-xs text-gray-600">- {param.description}</span>}
                  <button
                    type="button"
                    onClick={() => handleRemoveParam(index)}
                    className="ml-auto text-red-600 hover:text-red-800"
                  >
                    Remove
                  </button>
                </div>
              ))}
              
              <div className="flex space-x-2">
                <input
                  type="text"
                  placeholder="Name"
                  value={newParam.name}
                  onChange={(e) => setNewParam(prev => ({ ...prev, name: e.target.value }))}
                  className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
                <select
                  value={newParam.type}
                  onChange={(e) => setNewParam(prev => ({ ...prev, type: e.target.value }))}
                  className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="boolean">boolean</option>
                  <option value="array">array</option>
                  <option value="object">object</option>
                </select>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={newParam.required}
                    onChange={(e) => setNewParam(prev => ({ ...prev, required: e.target.checked }))}
                    className="rounded border-gray-300 text-indigo-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  />
                  <span className="ml-1 text-sm">Required</span>
                </label>
                <button
                  type="button"
                  onClick={handleAddParam}
                  className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                  Add
                </button>
              </div>
            </div>
          </div>

          {/* Resource-specific fields */}
          {formData.service_type === 'resource' && (
            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="text-md font-medium text-blue-900 mb-3">📄 Resource Configuration</h4>
              <div>
                <label className="block text-sm font-medium text-gray-700">MIME Type</label>
                <select
                  name="mime_type"
                  value={formData.mime_type}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="text/plain">text/plain</option>
                  <option value="text/html">text/html</option>
                  <option value="text/markdown">text/markdown</option>
                  <option value="application/json">application/json</option>
                  <option value="text/csv">text/csv</option>
                  <option value="application/xml">application/xml</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  MIME type of the content returned by this resource
                </p>
              </div>
            </div>
          )}

          {/* Prompt-specific fields */}
          {formData.service_type === 'prompt' && (
            <div className="bg-green-50 p-4 rounded-lg">
              <h4 className="text-md font-medium text-green-900 mb-3">💬 Prompt Configuration</h4>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700">Prompt Template</label>
                <textarea
                  name="prompt_template"
                  value={formData.prompt_template}
                  onChange={handleChange}
                  rows={4}
                  placeholder="Hello {name}! How can I help you with {topic}?"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Template with placeholders (e.g., {"{name}"}, {"{topic}"}). Arguments can be filled dynamically.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Prompt Arguments</label>
                <div className="space-y-2">
                  {formData.prompt_args.map((arg, index) => (
                    <div key={index} className="flex items-center space-x-2 bg-white p-2 rounded border">
                      <span className="text-sm">{arg.name} ({arg.type})</span>
                      <span className="text-xs text-gray-500">{arg.required ? 'Required' : 'Optional'}</span>
                      {arg.description && <span className="text-xs text-gray-600">- {arg.description}</span>}
                      <button
                        type="button"
                        onClick={() => handleRemovePromptArg(index)}
                        className="ml-auto text-red-600 hover:text-red-800"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      placeholder="Argument name"
                      value={newParam.name}
                      onChange={(e) => setNewParam(prev => ({ ...prev, name: e.target.value }))}
                      className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                    <select
                      value={newParam.type}
                      onChange={(e) => setNewParam(prev => ({ ...prev, type: e.target.value }))}
                      className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    >
                      <option value="string">string</option>
                      <option value="number">number</option>
                      <option value="boolean">boolean</option>
                    </select>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={newParam.required}
                        onChange={(e) => setNewParam(prev => ({ ...prev, required: e.target.checked }))}
                        className="rounded border-gray-300 text-indigo-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                      />
                      <span className="ml-1 text-sm">Required</span>
                    </label>
                    <button
                      type="button"
                      onClick={handleAddPromptArg}
                      className="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600"
                    >
                      Add Arg
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700">Code</label>
            <textarea
              name="code"
              value={formData.code}
              onChange={handleChange}
              rows={10}
              required
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono"
            />
          </div>

          {/* Output Schema field for tools */}
          {formData.service_type === 'tool' && (
            <div className="bg-indigo-50 p-4 rounded-lg space-y-4">
              <h4 className="text-md font-medium text-indigo-900">🔧 MCP Output Schema (Optional)</h4>
              
              <div>
                <label className="block text-sm font-medium text-gray-700">Output Schema (JSON Schema)</label>
                <textarea
                  name="output_schema"
                  value={formData.output_schema ? JSON.stringify(formData.output_schema, null, 2) : ''}
                  onChange={(e) => {
                    try {
                      const value = e.target.value.trim();
                      setFormData(prev => ({
                        ...prev,
                        output_schema: value ? JSON.parse(value) : null
                      }));
                    } catch (err) {
                      // Invalid JSON, keep as string temporarily
                      setFormData(prev => ({
                        ...prev,
                        output_schema: e.target.value
                      }));
                    }
                  }}
                  rows={6}
                  placeholder='{\n  "type": "object",\n  "properties": {\n    "result": {"type": "string"}\n  }\n}'
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono"
                />
                <p className="mt-1 text-xs text-gray-500">
                  JSON Schema that describes the output format. FastMCP 2.10+ will use this for structured output. Auto-generated if using AI.
                </p>
              </div>
            </div>
          )}


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