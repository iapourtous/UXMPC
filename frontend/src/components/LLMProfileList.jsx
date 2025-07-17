import React from 'react';
import { useLLMProfiles, useDeleteLLMProfile } from '../hooks/useLLMProfiles';

export default function LLMProfileList({ onEdit }) {
  const { data: profiles, isLoading, error } = useLLMProfiles();
  const deleteMutation = useDeleteLLMProfile();

  if (isLoading) return <div className="text-center py-4">Loading LLM profiles...</div>;
  if (error) return <div className="text-red-500 text-center py-4">Error loading LLM profiles</div>;

  const handleDelete = async (profile) => {
    if (window.confirm(`Are you sure you want to delete "${profile.name}"?`)) {
      try {
        await deleteMutation.mutateAsync(profile.id);
      } catch (err) {
        console.error('Failed to delete LLM profile:', err);
      }
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
              Model
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Endpoint
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Description
            </th>
            <th className="px-4 py-2 border-b text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Config
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
          {profiles?.map((profile) => (
            <tr key={profile.id} className="hover:bg-gray-50">
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                {profile.name}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                  {profile.model}
                </code>
              </td>
              <td className="px-4 py-2 text-sm text-gray-500 max-w-xs truncate">
                {profile.endpoint ? (
                  <span className="text-blue-600" title={profile.endpoint}>
                    {profile.endpoint.length > 30 ? profile.endpoint.substring(0, 30) + '...' : profile.endpoint}
                  </span>
                ) : (
                  <span className="text-gray-400 italic">Default</span>
                )}
              </td>
              <td className="px-4 py-2 text-sm text-gray-500 max-w-xs">
                {profile.description ? (
                  <span title={profile.description}>
                    {profile.description.length > 50 ? profile.description.substring(0, 50) + '...' : profile.description}
                  </span>
                ) : (
                  <span className="text-gray-400 italic">No description</span>
                )}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <div className="text-xs">
                  <div>Tokens: {profile.max_tokens}</div>
                  <div>Temp: {profile.temperature}</div>
                  <div className="capitalize">{profile.mode}</div>
                </div>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                  profile.active 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {profile.active ? 'Active' : 'Inactive'}
                </span>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm font-medium">
                <button
                  onClick={() => onEdit(profile)}
                  className="mr-2 px-3 py-1 text-xs font-medium rounded bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(profile)}
                  disabled={deleteMutation.isLoading}
                  className="px-3 py-1 text-xs font-medium rounded bg-red-100 text-red-700 hover:bg-red-200 transition-colors disabled:opacity-50"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {(!profiles || profiles.length === 0) && (
        <div className="text-center py-8 text-gray-500">
          No LLM profiles found. Create your first profile!
        </div>
      )}
    </div>
  );
}