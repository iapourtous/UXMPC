import React, { useEffect, useRef, useState } from 'react';
import vegaEmbed from 'vega-embed';

const VegaLiteBlock = ({ spec, theme = 'light', width = '100%', height = 400 }) => {
  const containerRef = useRef(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!spec || !containerRef.current) return;

    const embedSpec = async () => {
      try {
        setLoading(true);
        setError(null);

        // Clear previous content
        containerRef.current.innerHTML = '';

        // Prepare the spec with responsive width if not specified
        const fullSpec = {
          ...spec,
          width: spec.width || 'container',
          height: spec.height || height,
          autosize: spec.autosize || {
            type: 'fit',
            contains: 'padding'
          }
        };

        // Vega-Embed options
        const options = {
          theme: theme === 'dark' ? 'dark' : 'excel',
          actions: {
            export: true,
            source: false,
            compiled: false,
            editor: false
          },
          hover: true,
          renderer: 'svg',
          tooltip: true,
          downloadFileName: 'vega-chart'
        };

        // Embed the visualization
        const result = await vegaEmbed(containerRef.current, fullSpec, options);
        
        // Make it responsive
        if (fullSpec.width === 'container') {
          const resizeObserver = new ResizeObserver(() => {
            if (result && result.view) {
              result.view.width(containerRef.current.clientWidth - 40).run();
            }
          });
          resizeObserver.observe(containerRef.current);
          
          return () => resizeObserver.disconnect();
        }
      } catch (err) {
        console.error('Vega-Lite embedding error:', err);
        setError(err.message || 'Failed to render visualization');
      } finally {
        setLoading(false);
      }
    };

    embedSpec();
  }, [spec, theme, height]);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-300 rounded-xl p-4 my-4">
        <div className="text-red-700 font-semibold mb-2">Visualization Error</div>
        <div className="text-red-600 text-sm font-mono">{error}</div>
        <details className="mt-2">
          <summary className="cursor-pointer text-red-600 text-sm hover:text-red-800">
            Show specification
          </summary>
          <pre className="mt-2 text-xs bg-white p-2 rounded overflow-x-auto">
            {JSON.stringify(spec, null, 2)}
          </pre>
        </details>
      </div>
    );
  }

  return (
    <div className="vega-lite-container my-4">
      {loading && (
        <div className="flex items-center justify-center h-64 bg-gray-50 rounded-xl">
          <div className="text-gray-500">Loading visualization...</div>
        </div>
      )}
      <div 
        ref={containerRef}
        className="vega-embed-wrapper bg-white rounded-xl shadow-md p-4 overflow-x-auto"
        style={{ 
          width,
          minHeight: loading ? 0 : height,
          display: loading ? 'none' : 'block'
        }}
      />
    </div>
  );
};

export default VegaLiteBlock;