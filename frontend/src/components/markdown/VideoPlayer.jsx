import React, { useState } from 'react';
import ReactPlayer from 'react-player';

const VideoPlayer = ({ url, title = '', autoplay = false, loop = false, muted = false }) => {
  const [playing, setPlaying] = useState(autoplay);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  const handleError = (e) => {
    console.error('Video player error:', e);
    setError(true);
    setLoading(false);
  };

  const handleReady = () => {
    setLoading(false);
  };

  if (error) {
    return (
      <div className="bg-red-50 border border-red-300 rounded-xl p-4 my-4">
        <div className="text-red-700 font-semibold mb-2">Video Error</div>
        <div className="text-red-600 text-sm">
          Unable to load video from: {url}
        </div>
      </div>
    );
  }

  // Check if URL is supported by ReactPlayer
  const isSupported = ReactPlayer.canPlay(url);
  
  if (!isSupported) {
    // Fallback for unsupported URLs - try native video element
    if (/\.(mp4|webm|ogg)$/i.test(url)) {
      return (
        <div className="video-player-wrapper my-4 rounded-xl overflow-hidden shadow-lg bg-black">
          <video
            controls
            autoPlay={autoplay}
            loop={loop}
            muted={muted}
            className="w-full h-auto"
            style={{ maxHeight: '70vh' }}
            onError={handleError}
          >
            <source src={url} />
            Your browser does not support the video tag.
          </video>
          {title && (
            <div className="bg-gray-900 text-white px-4 py-2 text-sm">
              {title}
            </div>
          )}
        </div>
      );
    }
    
    return (
      <div className="bg-yellow-50 border border-yellow-300 rounded-xl p-4 my-4">
        <div className="text-yellow-700 font-semibold mb-2">Unsupported Video</div>
        <div className="text-yellow-600 text-sm">
          This video format is not supported. 
          <a href={url} target="_blank" rel="noopener noreferrer" className="ml-2 text-blue-600 underline">
            Open in new tab
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="video-player-container my-4">
      {loading && (
        <div className="flex items-center justify-center h-64 bg-gray-900 rounded-xl">
          <div className="text-white">Loading video...</div>
        </div>
      )}
      <div 
        className="video-player-wrapper rounded-xl overflow-hidden shadow-lg bg-black"
        style={{ display: loading ? 'none' : 'block' }}
      >
        <div className="relative" style={{ paddingTop: '56.25%' /* 16:9 aspect ratio */ }}>
          <ReactPlayer
            url={url}
            playing={playing}
            loop={loop}
            muted={muted}
            controls={true}
            width="100%"
            height="100%"
            style={{
              position: 'absolute',
              top: 0,
              left: 0
            }}
            onError={handleError}
            onReady={handleReady}
            config={{
              youtube: {
                playerVars: {
                  modestbranding: 1,
                  rel: 0
                }
              },
              vimeo: {
                playerOptions: {
                  title: true,
                  byline: false,
                  portrait: false
                }
              },
              file: {
                attributes: {
                  controlsList: 'nodownload'
                }
              }
            }}
          />
        </div>
        {title && (
          <div className="bg-gray-900 text-white px-4 py-2 text-sm">
            {title}
          </div>
        )}
      </div>
      
      {/* Video controls hint */}
      <div className="mt-2 text-xs text-gray-500 text-center">
        Click to play/pause • Fullscreen available
      </div>
    </div>
  );
};

export default VideoPlayer;