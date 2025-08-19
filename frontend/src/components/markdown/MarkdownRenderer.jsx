import React, { useMemo, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';
import mermaid from 'mermaid';
import VegaLiteBlock from './VegaLiteBlock';
import MediaGallery from './MediaGallery';
import VideoPlayer from './VideoPlayer';
import 'katex/dist/katex.min.css';
import 'react-image-gallery/styles/css/image-gallery.css';

// Initialize mermaid
mermaid.initialize({ 
  startOnLoad: true, 
  theme: 'default',
  securityLevel: 'loose',
  flowchart: {
    useMaxWidth: true,
    htmlLabels: true,
    curve: 'basis'
  },
  themeVariables: {
    primaryColor: '#4f46e5',
    primaryTextColor: '#fff',
    primaryBorderColor: '#7c3aed',
    lineColor: '#5b21b6',
    secondaryColor: '#8b5cf6',
    tertiaryColor: '#ddd6fe'
  }
});

const MarkdownRenderer = ({ content, className = '', onMediaClick, theme = 'light' }) => {
  // Preprocess content to normalize gallery syntax
  const processedContent = useMemo(() => {
    if (!content) return { text: '', mediaBlocks: [] };
    
    let processedText = content;
    const mediaBlocks = [];
    
    // Convert :::gallery syntax to ```gallery for consistent handling
    const galleryRegex = /:::gallery\n([\s\S]*?):::/g;
    processedText = processedText.replace(galleryRegex, (match, galleryContent) => {
      return '```gallery\n' + galleryContent + '\n```';
    });
    
    // Extract standalone videos (keeping this as-is for now)
    const videoRegex = /!\[([^\]]*)\]\((.*?\.(mp4|webm|ogg|youtube\.com|youtu\.be|vimeo\.com)[^\)]*)\)/g;
    processedText = processedText.replace(videoRegex, (match, alt, url) => {
      const id = `video-${Date.now()}-${Math.random()}`;
      mediaBlocks.push({ type: 'video', id, url, alt });
      return `<div data-video-id="${id}"></div>`;
    });
    
    return { text: processedText, mediaBlocks };
  }, [content]);

  // Render mermaid diagrams after content updates
  useEffect(() => {
    const renderMermaidDiagrams = async () => {
      // Small delay to ensure DOM is ready
      await new Promise(resolve => setTimeout(resolve, 100));
      
      const mermaidElements = document.querySelectorAll('.mermaid-to-render');
      
      for (const element of mermaidElements) {
        const graphDefinition = element.textContent;
        element.classList.remove('mermaid-to-render');
        element.classList.add('mermaid-rendered');
        
        // Clean up the diagram text (remove any CSS or HTML that might have leaked)
        const cleanedDefinition = graphDefinition
          .replace(/#mermaid-[\d-]+\{[^}]*\}/g, '') // Remove CSS rules
          .replace(/<[^>]*>/g, '') // Remove HTML tags
          .trim();
        
        if (!cleanedDefinition || cleanedDefinition.length < 10) {
          element.innerHTML = `
            <div class="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
              <div class="text-yellow-700 font-semibold mb-2">⚠️ Empty or Invalid Diagram</div>
              <div class="text-yellow-600 text-sm">The diagram definition appears to be empty or corrupted.</div>
            </div>
          `;
          continue;
        }
        
        try {
          // Generate unique ID
          const id = `mermaid-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
          
          // Try to parse and validate before rendering
          const { svg } = await mermaid.render(id, cleanedDefinition);
          element.innerHTML = svg;
        } catch (error) {
          console.error('Mermaid rendering error:', error);
          
          // Better error handling with suggestions
          let errorMessage = error.message || 'Unknown error';
          let suggestion = '';
          
          if (errorMessage.includes('Duplicate id')) {
            // Try again with a new ID
            try {
              const newId = `mermaid-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
              const { svg } = await mermaid.render(newId, cleanedDefinition);
              element.innerHTML = svg;
              return;
            } catch (retryError) {
              errorMessage = retryError.message;
            }
          }
          
          // Provide helpful suggestions based on error type
          if (errorMessage.includes('No diagram type detected')) {
            suggestion = 'Make sure the diagram starts with a valid type (graph, flowchart, sequenceDiagram, etc.)';
          } else if (errorMessage.includes('Syntax error')) {
            suggestion = 'Check the diagram syntax. Common issues: missing arrows (-->), unclosed quotes, or invalid node names.';
          } else if (errorMessage.includes('Parse error')) {
            suggestion = 'The diagram contains invalid Mermaid syntax. Verify node definitions and connections.';
          }
          
          element.innerHTML = `
            <div class="bg-red-50 border border-red-300 rounded-lg p-4">
              <div class="text-red-700 font-semibold mb-2">🔴 Diagram Rendering Error</div>
              <div class="text-red-600 text-sm mb-2">${errorMessage}</div>
              ${suggestion ? `<div class="text-red-500 text-sm italic">💡 ${suggestion}</div>` : ''}
              <details class="mt-3">
                <summary class="cursor-pointer text-red-600 text-sm hover:text-red-800">Show diagram code</summary>
                <pre class="mt-2 p-2 bg-white rounded text-xs overflow-x-auto">${cleanedDefinition}</pre>
              </details>
            </div>
          `;
        }
      }
    };

    renderMermaidDiagrams();
  }, [content]); // Trigger on content change

  const components = useMemo(() => ({
    // Handle code blocks
    pre: ({ node, children, ...props }) => {
      // Check if this is a code block with a language
      const codeChild = React.isValidElement(children) ? children : null;
      const codeClassName = codeChild?.props?.className || '';
      const languageMatch = /language-(\w+(-\w+)?)/.exec(codeClassName);
      const language = languageMatch ? languageMatch[1] : '';
      
      // Handle Gallery blocks
      if (language === 'gallery') {
        let galleryContent = '';
        
        // Extract text from the code element
        if (codeChild?.props?.children) {
          if (typeof codeChild.props.children === 'string') {
            galleryContent = codeChild.props.children;
          } else if (Array.isArray(codeChild.props.children)) {
            galleryContent = codeChild.props.children.join('');
          }
        }
        
        return <MediaGallery content={galleryContent} />;
      }
      
      // Handle Vega-Lite blocks
      if (language === 'vega-lite' || language === 'vega') {
        let vegaCode = '';
        
        // Extract text from the code element
        if (codeChild?.props?.children) {
          if (typeof codeChild.props.children === 'string') {
            vegaCode = codeChild.props.children;
          } else if (Array.isArray(codeChild.props.children)) {
            vegaCode = codeChild.props.children.join('');
          }
        }
        
        try {
          const spec = JSON.parse(vegaCode);
          return <VegaLiteBlock spec={spec} theme={theme} />;
        } catch (error) {
          console.error('Failed to parse Vega-Lite spec:', error);
          return (
            <pre className="bg-red-50 border border-red-300 rounded-xl p-4 text-red-700">
              Invalid Vega-Lite specification: {error.message}
            </pre>
          );
        }
      }
      
      // Handle Mermaid blocks (existing code)
      const classNames = node?.properties?.className || [];
      const isMermaid = classNames.some(cls => 
        cls === 'mermaid' || 
        cls === 'language-mermaid' ||
        cls?.includes('mermaid')
      ) || language === 'mermaid';
      
      if (isMermaid) {
        let mermaidCode = '';
        if (typeof children === 'string') {
          mermaidCode = children;
        } else if (children?.props?.children) {
          if (typeof children.props.children === 'string') {
            mermaidCode = children.props.children;
          } else if (Array.isArray(children.props.children)) {
            mermaidCode = children.props.children.join('');
          }
        } else if (React.isValidElement(children)) {
          const extractText = (element) => {
            if (typeof element === 'string') return element;
            if (Array.isArray(element)) return element.map(extractText).join('');
            if (element?.props?.children) return extractText(element.props.children);
            return '';
          };
          mermaidCode = extractText(children);
        }
        
        return (
          <div className="mermaid-to-render bg-white border rounded-xl p-6 overflow-x-auto shadow-md my-4">
            {mermaidCode}
          </div>
        );
      }
      
      return <pre className="bg-gray-50 border rounded-xl p-4 overflow-x-auto shadow-inner" {...props}>{children}</pre>;
    },
    
    // Handle inline code and code blocks
    code: ({ node, inline, className, children, ...props }) => {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';
      
      // Debug vega-lite blocks
      if (!inline && language === 'vega-lite') {
        console.log('Processing vega-lite block:', {
          className,
          language,
          childrenType: typeof children,
          childrenContent: children
        });
        
        try {
          const spec = typeof children === 'string' 
            ? JSON.parse(children)
            : JSON.parse(String(children));
          console.log('Parsed vega-lite spec successfully:', spec);
          return <VegaLiteBlock spec={spec} theme={theme} />;
        } catch (error) {
          console.error('Failed to parse vega-lite:', error, 'Children was:', children);
          return (
            <pre className="bg-red-50 border border-red-300 rounded-xl p-4 text-red-700">
              Invalid Vega-Lite specification: {error.message}
              <br/>
              Raw content: {String(children).substring(0, 200)}...
            </pre>
          );
        }
      }
      
      // Handle mermaid
      if (!inline && language === 'mermaid') {
        return (
          <div className="mermaid-to-render bg-gray-50 border rounded-xl p-4 overflow-x-auto shadow-inner">
            {children}
          </div>
        );
      }
      
      // Regular code blocks
      if (!inline && language) {
        return (
          <div className="relative group">
            <div className="absolute top-2 right-2 text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
              {language}
            </div>
            <pre className="bg-gray-900 text-gray-100 rounded-xl p-4 overflow-x-auto shadow-lg">
              <code className={className} {...props}>
                {children}
              </code>
            </pre>
          </div>
        );
      }
      
      // Inline code
      if (inline) {
        return (
          <code className="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
            {children}
          </code>
        );
      }
      
      return <code className={className} {...props}>{children}</code>;
    },
    
    // Handle images with lazy loading
    img: ({ node, src, alt, ...props }) => {
      // Check if this is part of a gallery or video (handled separately)
      if (node?.properties?.['data-media-id'] || node?.properties?.['data-video-id']) {
        return null;
      }
      
      return (
        <figure className="my-4">
          <img 
            src={src} 
            alt={alt} 
            loading="lazy"
            className="rounded-lg shadow-lg max-w-full h-auto cursor-pointer hover:shadow-xl transition-shadow"
            onClick={() => onMediaClick && onMediaClick({ type: 'image', src, alt })}
            {...props}
          />
          {alt && (
            <figcaption className="text-sm text-gray-600 text-center mt-2 italic">
              {alt}
            </figcaption>
          )}
        </figure>
      );
    },
    
    // Handle custom div elements for media (mainly for videos now)
    div: ({ node, ...props }) => {
      const videoId = node?.properties?.['data-video-id'];
      
      if (videoId) {
        const videoBlock = processedContent.mediaBlocks.find(block => block.id === videoId);
        if (videoBlock && videoBlock.type === 'video') {
          return <VideoPlayer url={videoBlock.url} title={videoBlock.alt} />;
        }
      }
      
      return <div {...props} />;
    },
    
    // Enhanced typography
    h1: ({ children, ...props }) => (
      <h1 className="text-3xl font-bold mt-6 mb-4 text-gray-900 border-b pb-2" {...props}>
        {children}
      </h1>
    ),
    h2: ({ children, ...props }) => (
      <h2 className="text-2xl font-semibold mt-5 mb-3 text-gray-800" {...props}>
        {children}
      </h2>
    ),
    h3: ({ children, ...props }) => (
      <h3 className="text-xl font-semibold mt-4 mb-2 text-gray-800" {...props}>
        {children}
      </h3>
    ),
    p: ({ children, ...props }) => (
      <p className="my-3 leading-relaxed text-gray-700" {...props}>
        {children}
      </p>
    ),
    ul: ({ children, ...props }) => (
      <ul className="list-disc list-inside my-3 space-y-1 text-gray-700" {...props}>
        {children}
      </ul>
    ),
    ol: ({ children, ...props }) => (
      <ol className="list-decimal list-inside my-3 space-y-1 text-gray-700" {...props}>
        {children}
      </ol>
    ),
    blockquote: ({ children, ...props }) => (
      <blockquote className="border-l-4 border-blue-500 pl-4 my-4 italic text-gray-600" {...props}>
        {children}
      </blockquote>
    ),
    table: ({ children, ...props }) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full border-collapse border border-gray-300" {...props}>
          {children}
        </table>
      </div>
    ),
    th: ({ children, ...props }) => (
      <th className="border border-gray-300 px-4 py-2 bg-gray-100 font-semibold text-left" {...props}>
        {children}
      </th>
    ),
    td: ({ children, ...props }) => (
      <td className="border border-gray-300 px-4 py-2" {...props}>
        {children}
      </td>
    ),
    a: ({ children, href, ...props }) => (
      <a 
        href={href} 
        className="text-blue-600 hover:text-blue-800 underline"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    ),
    hr: ({ ...props }) => (
      <hr className="my-6 border-t border-gray-300" {...props} />
    ),
  }), [processedContent.mediaBlocks, onMediaClick, theme]);

  return (
    <div className={`markdown-renderer ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
        components={components}
      >
        {processedContent.text}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;