import React from 'react';

export default function TestResultModal({ isOpen, onClose, results }) {
  if (!isOpen) return null;
  
  // Handle loading or error states
  if (!results) {
    return (
      <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
        <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
          <div className="text-center">
            <p>Loading test results...</p>
          </div>
        </div>
      </div>
    );
  }

  const getStatusColor = (status) => {
    if (status >= 200 && status < 300) return 'text-green-600';
    if (status >= 400 && status < 500) return 'text-yellow-600';
    if (status >= 500) return 'text-red-600';
    return 'text-gray-600';
  };

  const getValidationColor = (valid) => {
    return valid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800';
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-6xl shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-gray-900">
            Test Results: {results.service?.name || 'Unknown Service'}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mb-4 p-4 bg-gray-50 rounded">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <span className="text-sm text-gray-500">Service Type:</span>
              <p className="font-medium">{results.service?.type || 'N/A'}</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">Route:</span>
              <p className="font-medium">{results.service?.route || 'N/A'}</p>
            </div>
            <div>
              <span className="text-sm text-gray-500">LLM Profile:</span>
              <p className="font-medium">{results.llm_profile || 'N/A'}</p>
            </div>
          </div>
        </div>

        <div className="mb-4">
          <h4 className="font-semibold mb-2">Summary</h4>
          <div className="grid grid-cols-4 gap-4 text-center">
            <div className="p-3 bg-blue-50 rounded">
              <p className="text-2xl font-bold text-blue-600">{results.summary?.total || 0}</p>
              <p className="text-sm text-gray-600">Total Tests</p>
            </div>
            <div className="p-3 bg-green-50 rounded">
              <p className="text-2xl font-bold text-green-600">{results.summary?.passed || 0}</p>
              <p className="text-sm text-gray-600">Passed</p>
            </div>
            <div className="p-3 bg-red-50 rounded">
              <p className="text-2xl font-bold text-red-600">{results.summary?.failed || 0}</p>
              <p className="text-sm text-gray-600">Failed</p>
            </div>
            <div className="p-3 bg-purple-50 rounded">
              <p className="text-2xl font-bold text-purple-600">{results.summary?.success_rate || '0%'}</p>
              <p className="text-sm text-gray-600">Success Rate</p>
            </div>
          </div>
        </div>

        <div className="space-y-4 max-h-96 overflow-y-auto">
          {results.results && results.results.length > 0 ? (
            results.results.map((result, index) => (
            <div key={index} className="border rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <h5 className="font-semibold">{result.test_case?.name || 'Unnamed Test'}</h5>
                <span className={`px-2 py-1 text-xs rounded ${getValidationColor(result.validation?.valid)}`}>
                  {result.validation?.valid ? '✓ PASS' : '✗ FAIL'}
                </span>
              </div>
              
              <p className="text-sm text-gray-600 mb-2">{result.test_case?.description || ''}</p>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h6 className="text-xs font-semibold text-gray-700 mb-1">Parameters</h6>
                  <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                    {JSON.stringify(result.test_case?.params || {}, null, 2)}
                  </pre>
                </div>
                
                <div>
                  <h6 className="text-xs font-semibold text-gray-700 mb-1">Response</h6>
                  <div className="text-xs bg-gray-100 p-2 rounded">
                    <p className={`font-semibold ${getStatusColor(result.execution?.status || 0)}`}>
                      Status: {result.execution?.status || 'Unknown'}
                    </p>
                    {result.execution?.error ? (
                      <p className="text-red-600 mt-1">Error: {result.execution.error}</p>
                    ) : (
                      <pre className="mt-1 overflow-x-auto">
                        {JSON.stringify(result.execution?.response || {}, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              </div>
              
              {result.validation?.issues && result.validation.issues.length > 0 && (
                <div className="mt-2">
                  <h6 className="text-xs font-semibold text-gray-700 mb-1">Issues</h6>
                  <ul className="text-xs text-red-600 list-disc list-inside">
                    {result.validation.issues.map((issue, i) => (
                      <li key={i}>
                        {typeof issue === 'string' 
                          ? issue 
                          : typeof issue === 'object' && issue !== null
                            ? (() => {
                                // Handle complex issue objects with expected/actual
                                if (issue.issue && (issue.expected || issue.actual)) {
                                  return (
                                    <div>
                                      <span>{issue.issue}</span>
                                      {issue.expected && (
                                        <div className="ml-4 mt-1">
                                          <span className="font-semibold">Expected:</span> {JSON.stringify(issue.expected)}
                                        </div>
                                      )}
                                      {issue.actual && (
                                        <div className="ml-4">
                                          <span className="font-semibold">Actual:</span> {JSON.stringify(issue.actual)}
                                        </div>
                                      )}
                                    </div>
                                  );
                                }
                                // Fallback for other object types
                                return issue.issue || issue.message || JSON.stringify(issue);
                              })()
                            : String(issue)
                        }
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              <div className="mt-2">
                <p className="text-xs text-gray-600">
                  <span className="font-semibold">Validation Summary:</span> {result.validation?.summary || 'No summary available'}
                </p>
              </div>
            </div>
          ))) : (
            <div className="text-center text-gray-500 py-4">
              No test results available
            </div>
          )}
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-300 text-black rounded hover:bg-gray-400"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}