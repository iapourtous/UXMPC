import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useServices, useActivateService, useDeactivateService, useDeleteService } from '../hooks/useServices';
import TestResultModal from './TestResultModal';
import ServiceLogs from './ServiceLogs';

export default function ServiceList() {
  const navigate = useNavigate();
  const { data: services, isLoading, error } = useServices();
  const activateMutation = useActivateService();
  const deactivateMutation = useDeactivateService();
  const deleteMutation = useDeleteService();
  
  const [testResults, setTestResults] = useState(null);
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [testingServiceId, setTestingServiceId] = useState(null);
  const [logsService, setLogsService] = useState(null);

  if (isLoading) return <div className="text-center py-4">Loading services...</div>;
  if (error) return <div className="text-red-500 text-center py-4">Error loading services</div>;

  const handleToggle = async (service) => {
    try {
      if (service.active) {
        await deactivateMutation.mutateAsync(service.id);
      } else {
        await activateMutation.mutateAsync(service.id);
      }
    } catch (err) {
      console.error('Failed to toggle service:', err);
    }
  };

  const handleDelete = async (service) => {
    if (window.confirm(`Are you sure you want to delete "${service.name}"?`)) {
      try {
        await deleteMutation.mutateAsync(service.id);
      } catch (err) {
        console.error('Failed to delete service:', err);
      }
    }
  };

  const handleTest = async (service) => {
    try {
      setTestingServiceId(service.id);
      const response = await fetch(`http://localhost:8000/services/${service.id}/test`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        const error = await response.json();
        alert(error.detail || 'Failed to test service');
        return;
      }
      
      const results = await response.json();
      console.log('Test results:', results); // Debug log
      setTestResults(results);
      setIsTestModalOpen(true);
    } catch (err) {
      console.error('Failed to test service:', err);
      alert('Failed to test service: ' + err.message);
    } finally {
      setTestingServiceId(null);
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full bg-white border border-gray-300">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Name
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Type
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Route
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Method
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {services?.map((service) => (
            <tr key={service.id} className="hover:bg-gray-50">
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                {service.name}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                  service.service_type === 'tool' ? 'bg-orange-100 text-orange-800' :
                  service.service_type === 'resource' ? 'bg-blue-100 text-blue-800' :
                  service.service_type === 'prompt' ? 'bg-green-100 text-green-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {service.service_type === 'tool' && '🔧 Tool'}
                  {service.service_type === 'resource' && '📄 Resource'}
                  {service.service_type === 'prompt' && '💬 Prompt'}
                  {!service.service_type && 'Unknown'}
                </span>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                {service.route}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <span className="px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                  {service.method}
                </span>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                  service.active 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {service.active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium">
                <button
                  onClick={() => handleToggle(service)}
                  disabled={activateMutation.isLoading || deactivateMutation.isLoading}
                  className={`mr-2 px-3 py-1 text-xs font-medium rounded ${
                    service.active
                      ? 'bg-red-100 text-red-700 hover:bg-red-200'
                      : 'bg-green-100 text-green-700 hover:bg-green-200'
                  } transition-colors disabled:opacity-50`}
                >
                  {service.active ? 'Deactivate' : 'Activate'}
                </button>
                <button
                  onClick={() => navigate(`/services/${service.id}/edit`)}
                  className="mr-2 px-3 py-1 text-xs font-medium rounded bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
                >
                  Edit
                </button>
                {service.llm_profile && (
                  <button
                    onClick={() => handleTest(service)}
                    disabled={testingServiceId === service.id}
                    className="mr-2 px-3 py-1 text-xs font-medium rounded bg-purple-100 text-purple-700 hover:bg-purple-200 transition-colors disabled:opacity-50"
                  >
                    {testingServiceId === service.id ? 'Testing...' : 'Test'}
                  </button>
                )}
                <button
                  onClick={() => setLogsService(service)}
                  className="mr-2 px-3 py-1 text-xs font-medium rounded bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                >
                  Logs
                </button>
                <button
                  onClick={() => handleDelete(service)}
                  disabled={service.active || deleteMutation.isLoading}
                  className="px-3 py-1 text-xs font-medium rounded bg-red-100 text-red-700 hover:bg-red-200 transition-colors disabled:opacity-50"
                  title={service.active ? "Deactivate service first" : "Delete service"}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {(!services || services.length === 0) && (
        <div className="text-center py-8 text-gray-500">
          No services found. Create your first service!
        </div>
      )}
      
      {isTestModalOpen && (
        <TestResultModal
          isOpen={isTestModalOpen}
          onClose={() => setIsTestModalOpen(false)}
          results={testResults}
        />
      )}
      
      {logsService && (
        <ServiceLogs
          serviceId={logsService.id}
          serviceName={logsService.name}
          onClose={() => setLogsService(null)}
        />
      )}
    </div>
  );
}