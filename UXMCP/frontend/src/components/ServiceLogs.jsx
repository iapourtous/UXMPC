import React, { useState, useEffect, useRef } from 'react';
import { format } from 'date-fns';

const LOG_LEVELS = {
  DEBUG: { color: 'text-gray-600', bg: 'bg-gray-100', icon: '🔍' },
  INFO: { color: 'text-blue-600', bg: 'bg-blue-100', icon: 'ℹ️' },
  WARNING: { color: 'text-yellow-600', bg: 'bg-yellow-100', icon: '⚠️' },
  ERROR: { color: 'text-red-600', bg: 'bg-red-100', icon: '❌' },
  CRITICAL: { color: 'text-purple-600', bg: 'bg-purple-100', icon: '🔥' }
};

export default function ServiceLogs({ serviceId, serviceName, onClose, executionId, embedded = false }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [stats, setStats] = useState(null);
  const logsEndRef = useRef(null);
  const intervalRef = useRef(null);

  const fetchLogs = async () => {
    try {
      let url;
      const params = new URLSearchParams({
        limit: 100
      });
      
      if (executionId) {
        // If executionId is provided, fetch logs for that specific execution
        url = `http://localhost:8000/logs/execution/${executionId}`;
      } else {
        // Otherwise fetch logs for the service
        if (filter !== 'ALL') {
          params.append('level', filter);
        }
        
        if (search) {
          params.append('search', search);
        }
        
        url = `http://localhost:8000/logs/services/${serviceId}?${params}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch logs');
      
      const data = await response.json();
      setLogs(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`http://localhost:8000/logs/services/stats/${serviceId}?hours=24`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  useEffect(() => {
    fetchLogs();
    fetchStats();

    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        fetchLogs();
        fetchStats();
      }, 5000); // Refresh every 5 seconds
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [serviceId, filter, search, autoRefresh]);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const formatTimestamp = (timestamp) => {
    return format(new Date(timestamp), 'HH:mm:ss.SSS');
  };

  const formatDate = (timestamp) => {
    return format(new Date(timestamp), 'yyyy-MM-dd');
  };

  const renderLogDetails = (details) => {
    if (!details || Object.keys(details).length === 0) return null;
    
    return (
      <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
        <pre className="whitespace-pre-wrap break-words">
          {JSON.stringify(details, null, 2)}
        </pre>
      </div>
    );
  };

  const clearOldLogs = async () => {
    if (!window.confirm('Delete logs older than 7 days?')) return;
    
    try {
      const response = await fetch(`http://localhost:8000/logs/services/${serviceId}/old?days=7`, {
        method: 'DELETE'
      });
      
      if (!response.ok) throw new Error('Failed to delete logs');
      
      const result = await response.json();
      alert(result.message);
      fetchLogs();
    } catch (err) {
      alert('Failed to delete logs: ' + err.message);
    }
  };

  // If embedded, don't show as modal
  if (embedded) {
    return (
      <div className="bg-white rounded-lg shadow">
        <div className="p-4">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-gray-900">
              Execution Logs
            </h3>
            {stats && (
              <div className="flex gap-4 text-sm text-gray-600">
                <span>Total: {stats.total}</span>
                {stats.error > 0 && <span className="text-red-600">Errors: {stats.error}</span>}
              </div>
            )}
          </div>

          {!executionId && (
            <div className="mb-4 flex gap-4 items-center">
              <div className="flex gap-2">
                <button
                  onClick={() => setFilter('ALL')}
                  className={`px-3 py-1 rounded ${filter === 'ALL' ? 'bg-gray-800 text-white' : 'bg-gray-200'}`}
                >
                  All
                </button>
                {Object.keys(LOG_LEVELS).map(level => (
                  <button
                    key={level}
                    onClick={() => setFilter(level)}
                    className={`px-3 py-1 rounded ${filter === level ? LOG_LEVELS[level].bg + ' ' + LOG_LEVELS[level].color : 'bg-gray-200'}`}
                  >
                    {LOG_LEVELS[level].icon} {level}
                  </button>
                ))}
              </div>
            </div>
          )}

          {loading && <div className="text-center py-4">Loading logs...</div>}
          {error && <div className="text-red-500 text-center py-4">Error: {error}</div>}
          
          {!loading && !error && logs.length === 0 && (
            <div className="text-gray-500 text-center py-4">No logs found</div>
          )}
          
          {!loading && !error && logs.length > 0 && (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {logs.map((log, index) => {
                const logLevel = LOG_LEVELS[log.level] || LOG_LEVELS.INFO;
                return (
                  <div key={log.id || index} className={`p-3 rounded ${logLevel.bg}`}>
                    <div className="flex items-start gap-3">
                      <span className="text-lg">{logLevel.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-gray-600 font-mono">
                            {formatTimestamp(log.timestamp)}
                          </span>
                          <span className={`text-xs font-semibold ${logLevel.color}`}>
                            {log.level}
                          </span>
                        </div>
                        <div className="text-sm">{log.message}</div>
                        {renderLogDetails(log.details)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>
      </div>
    );
  }

  // Original modal view for non-embedded usage
  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-10 mx-auto p-5 border w-full max-w-7xl shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-900">
              Service Logs: {serviceName}
            </h3>
            {stats && (
              <div className="flex gap-4 text-sm text-gray-600 mt-1">
                <span>Total: {stats.total}</span>
                <span>Executions: {stats.executions}</span>
                {stats.error > 0 && <span className="text-red-600">Errors: {stats.error}</span>}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mb-4 flex gap-4 items-center">
          <div className="flex gap-2">
            <button
              onClick={() => setFilter('ALL')}
              className={`px-3 py-1 rounded ${filter === 'ALL' ? 'bg-gray-800 text-white' : 'bg-gray-200'}`}
            >
              All
            </button>
            {Object.keys(LOG_LEVELS).map(level => (
              <button
                key={level}
                onClick={() => setFilter(level)}
                className={`px-3 py-1 rounded ${filter === level ? LOG_LEVELS[level].bg + ' ' + LOG_LEVELS[level].color : 'bg-gray-200'}`}
              >
                {LOG_LEVELS[level].icon} {level}
              </button>
            ))}
          </div>

          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-3 py-1 border rounded flex-1"
          />

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span className="text-sm">Auto-refresh</span>
          </label>

          <button
            onClick={clearOldLogs}
            className="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
          >
            Clear Old
          </button>
        </div>

        <div className="bg-gray-900 text-gray-100 p-4 rounded-lg h-96 overflow-y-auto font-mono text-sm">
          {loading && <div className="text-center">Loading logs...</div>}
          {error && <div className="text-red-400">Error: {error}</div>}
          
          {!loading && logs.length === 0 && (
            <div className="text-center text-gray-500">No logs found</div>
          )}

          {logs.map((log, index) => {
            const levelStyle = LOG_LEVELS[log.level] || LOG_LEVELS.INFO;
            const isNewDay = index === 0 || 
              formatDate(log.timestamp) !== formatDate(logs[index - 1].timestamp);
            
            return (
              <div key={log.id}>
                {isNewDay && (
                  <div className="text-center text-gray-500 text-xs my-2">
                    ─── {formatDate(log.timestamp)} ───
                  </div>
                )}
                <div className="mb-3 hover:bg-gray-800 p-2 rounded">
                  <div className="flex items-start gap-2">
                    <span className="text-gray-500">{formatTimestamp(log.timestamp)}</span>
                    <span className={`${levelStyle.color} font-semibold`}>
                      [{log.level}]
                    </span>
                    <span className="flex-1">{log.message}</span>
                  </div>
                  {log.details && renderLogDetails(log.details)}
                  {log.execution_id && (
                    <div className="text-xs text-gray-600 mt-1">
                      Execution: {log.execution_id.substring(0, 8)}...
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={logsEndRef} />
        </div>

        <div className="mt-4 flex justify-between items-center">
          <div className="text-sm text-gray-600">
            Showing {logs.length} logs
          </div>
          <button
            onClick={scrollToBottom}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
          >
            Scroll to Bottom ↓
          </button>
        </div>
      </div>
    </div>
  );
}