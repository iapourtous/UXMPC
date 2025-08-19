import React, { useState, useMemo } from 'react';
import ImageGallery from 'react-image-gallery';
import { LazyLoadImage } from 'react-lazy-load-image-component';
import 'react-lazy-load-image-component/src/effects/blur.css';

const MediaGallery = ({ content }) => {
  const [showFullscreen, setShowFullscreen] = useState(false);
  
  // Helper function to extract YouTube video ID
  const extractYouTubeId = (url) => {
    const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    return match ? match[1] : '';
  };
  
  // Generate thumbnail URL (for videos, you might want to extract from video or use a placeholder)
  const getThumbnail = (url, alt) => {
    if (url.includes('youtube.com') || url.includes('youtu.be')) {
      const videoId = extractYouTubeId(url);
      return `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
    }
    if (url.includes('vimeo.com')) {
      // Vimeo thumbnails require API call, using placeholder
      return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'%3E%3Crect fill='%23333' width='320' height='180'/%3E%3Ctext fill='%23aaa' font-family='sans-serif' font-size='16' x='50%25' y='50%25' text-anchor='middle' dominant-baseline='middle'%3E${alt || 'Video'}%3C/text%3E%3C/svg%3E`;
    }
    // For regular images and local videos, use the same URL
    return url;
  };
  
  const renderVideo = (url, alt) => {
    if (url.includes('youtube.com') || url.includes('youtu.be')) {
      const videoId = extractYouTubeId(url);
      return (
        <div className="video-wrapper" style={{ position: 'relative', paddingBottom: '56.25%', height: 0 }}>
          <iframe
            src={`https://www.youtube.com/embed/${videoId}`}
            title={alt}
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%'
            }}
          />
        </div>
      );
    }
    
    if (url.includes('vimeo.com')) {
      const videoId = url.match(/vimeo\.com\/(\d+)/)?.[1];
      return (
        <div className="video-wrapper" style={{ position: 'relative', paddingBottom: '56.25%', height: 0 }}>
          <iframe
            src={`https://player.vimeo.com/video/${videoId}`}
            title={alt}
            frameBorder="0"
            allow="autoplay; fullscreen; picture-in-picture"
            allowFullScreen
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%'
            }}
          />
        </div>
      );
    }
    
    // Local video files
    return (
      <video 
        controls 
        className="w-full h-auto"
        style={{ maxHeight: '70vh' }}
      >
        <source src={url} />
        Your browser does not support the video tag.
      </video>
    );
  };
  
  const renderVideoThumb = (url, alt) => {
    return (
      <div className="relative">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-black bg-opacity-50 rounded-full p-3">
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path d="M6.5 5.5v9l7-4.5z" />
            </svg>
          </div>
        </div>
        <LazyLoadImage
          src={getThumbnail(url, alt)}
          alt={alt}
          effect="blur"
          className="w-full h-full object-cover"
        />
      </div>
    );
  };
  
  // Parse media items from content
  const items = useMemo(() => {
    if (!content) return [];
    
    const mediaItems = [];
    const lines = content.split('\n').filter(line => line.trim());
    
    lines.forEach(line => {
      // Parse markdown image/video syntax: ![alt](url)
      const match = line.match(/!\[([^\]]*)\]\(([^)]+)\)/);
      if (match) {
        const [, alt, url] = match;
        const isVideo = /\.(mp4|webm|ogg)$/i.test(url) || 
                       url.includes('youtube.com') || 
                       url.includes('youtu.be') || 
                       url.includes('vimeo.com');
        
        if (isVideo) {
          // For videos, we'll create a custom render
          mediaItems.push({
            original: url,
            thumbnail: getThumbnail(url, alt),
            description: alt,
            renderItem: () => renderVideo(url, alt),
            renderThumbInner: () => renderVideoThumb(url, alt),
            isVideo: true
          });
        } else {
          // For images
          mediaItems.push({
            original: url,
            thumbnail: getThumbnail(url, alt),
            description: alt,
            originalAlt: alt,
            thumbnailAlt: alt,
            isVideo: false
          });
        }
      }
    });
    
    return mediaItems;
  }, [content]);
  
  if (items.length === 0) {
    return (
      <div className="bg-gray-100 rounded-xl p-4 my-4 text-gray-500 text-center">
        No media items found in gallery
      </div>
    );
  }
  
  if (items.length === 1) {
    // Single item - display without gallery controls
    const item = items[0];
    if (item.isVideo) {
      return (
        <div className="my-4 rounded-xl overflow-hidden shadow-lg">
          {renderVideo(item.original, item.description)}
          {item.description && (
            <p className="text-sm text-gray-600 text-center mt-2 italic">
              {item.description}
            </p>
          )}
        </div>
      );
    }
    
    return (
      <figure className="my-4">
        <LazyLoadImage
          src={item.original}
          alt={item.description}
          effect="blur"
          className="rounded-xl shadow-lg w-full h-auto cursor-pointer hover:shadow-xl transition-shadow"
          onClick={() => setShowFullscreen(true)}
        />
        {item.description && (
          <figcaption className="text-sm text-gray-600 text-center mt-2 italic">
            {item.description}
          </figcaption>
        )}
      </figure>
    );
  }
  
  // Multiple items - show gallery
  return (
    <div className="media-gallery my-4 rounded-xl overflow-hidden shadow-lg bg-gray-50">
      <ImageGallery
        items={items}
        showPlayButton={false}
        showFullscreenButton={true}
        showNav={items.length > 1}
        showThumbnails={items.length > 1}
        lazyLoad={true}
        additionalClass="custom-image-gallery"
        renderItem={(item) => {
          if (item.isVideo) {
            return item.renderItem();
          }
          // Default image rendering with lazy loading
          return (
            <div className="image-gallery-image">
              <LazyLoadImage
                src={item.original}
                alt={item.originalAlt}
                effect="blur"
                className="w-full h-auto"
                style={{ maxHeight: '70vh', objectFit: 'contain' }}
              />
              {item.description && (
                <span className="image-gallery-description">
                  {item.description}
                </span>
              )}
            </div>
          );
        }}
      />
    </div>
  );
};

export default MediaGallery;