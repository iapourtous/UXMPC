"""
URL Extractor for COT Adaptive Engine
Robust URL extraction and validation with context awareness
"""
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse
import logging

logger = logging.getLogger(__name__)


class URLExtractor:
    """Advanced URL extraction and validation for COT"""
    
    def __init__(self):
        """Initialize URL extractor with comprehensive patterns"""
        
        # Main URL pattern - more comprehensive
        self.url_pattern = re.compile(
            r'(?:(?:https?|ftp|ftps|ssh|git|ws|wss):\/\/)?'  # Protocol (optional)
            r'(?:'
            r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}\.?|'  # Domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # IPv4
            r'\[?[A-F0-9]*:[A-F0-9:]+\]?'  # IPv6
            r')'
            r'(?::\d+)?'  # Port (optional)
            r'(?:/?|[/?]\S+?)' # Path
            r'(?=["\'\s,;!?\)\]\}]|$)',  # Lookahead for end
            re.IGNORECASE
        )
        
        # Special patterns for common services
        self.special_patterns = {
            'github': re.compile(r'github\.com/[\w-]+/[\w.-]+(?:/[\w./%-]*)?', re.IGNORECASE),
            'arxiv': re.compile(r'arxiv\.org/(?:abs|pdf)/\d+\.\d+(?:v\d+)?', re.IGNORECASE),
            'doi': re.compile(r'(?:doi\.org/|doi:|DOI:)\s*10\.\d{4,}/[\w./-]+', re.IGNORECASE),
            'youtube': re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+', re.IGNORECASE),
            'twitter': re.compile(r'(?:twitter|x)\.com/[\w]+/status/\d+', re.IGNORECASE),
        }
        
        # Exclude patterns for filtering
        self.exclude_patterns = [
            re.compile(r'localhost', re.IGNORECASE),
            re.compile(r'127\.0\.0\.1'),
            re.compile(r'192\.168\.\d+\.\d+'),
            re.compile(r'10\.\d+\.\d+\.\d+'),
            re.compile(r'example\.(?:com|org|net)', re.IGNORECASE),
            re.compile(r'test\.', re.IGNORECASE),
            re.compile(r'\.local$', re.IGNORECASE),
        ]
        
        # Common URL endings to clean
        self.trailing_chars = '.,;:!?\'")}]>'
        
    def extract_and_validate(self, text: str, max_urls: int = 100) -> List[Dict[str, str]]:
        """
        Extract and validate URLs from text with context
        
        Args:
            text: Text to extract URLs from
            max_urls: Maximum number of URLs to return
            
        Returns:
            List of URL dictionaries with url, context, and confidence
        """
        urls = []
        seen_urls = set()
        
        # First, try special patterns for known services
        for service_name, pattern in self.special_patterns.items():
            for match in pattern.finditer(text):
                url = match.group(0)
                url = self._clean_url(url, service_name)
                
                if url not in seen_urls and self._is_valid_url(url):
                    context = self._extract_context(text, match.start(), match.end())
                    urls.append({
                        "url": url,
                        "context": context,
                        "confidence": 0.95,  # High confidence for special patterns
                        "service": service_name
                    })
                    seen_urls.add(url)
        
        # Then use general pattern
        for match in self.url_pattern.finditer(text):
            url = match.group(0)
            url = self._clean_url(url)
            
            if url not in seen_urls and self._is_valid_url(url):
                context = self._extract_context(text, match.start(), match.end())
                confidence = self._calculate_url_confidence(url, context)
                
                if confidence > 0.3:  # Minimum confidence threshold
                    urls.append({
                        "url": url,
                        "context": context,
                        "confidence": confidence,
                        "service": self._identify_service(url)
                    })
                    seen_urls.add(url)
        
        # Sort by confidence and limit
        urls.sort(key=lambda x: x['confidence'], reverse=True)
        return urls[:max_urls]
    
    def _clean_url(self, url: str, service: Optional[str] = None) -> str:
        """
        Clean and normalize URL
        
        Args:
            url: Raw URL string
            service: Optional service name for special handling
            
        Returns:
            Cleaned URL
        """
        # Remove trailing punctuation
        url = url.rstrip(self.trailing_chars)
        
        # Remove wrapping characters
        if url.startswith('(') and url.endswith(')'):
            url = url[1:-1]
        if url.startswith('[') and url.endswith(']'):
            url = url[1:-1]
        if url.startswith('<') and url.endswith('>'):
            url = url[1:-1]
        
        # Add protocol if missing (except for DOI)
        if service == 'doi' and not url.startswith('http'):
            if url.startswith('doi:') or url.startswith('DOI:'):
                url = 'https://doi.org/' + url[4:].strip()
            elif not url.startswith('https://doi.org/'):
                url = 'https://doi.org/' + url
        elif not url.startswith(('http://', 'https://', 'ftp://', 'ftps://')):
            # Check if it looks like a valid domain
            if '.' in url and not url.startswith('.'):
                url = 'https://' + url
        
        # Special handling for arXiv
        if service == 'arxiv' and 'arxiv.org' in url:
            if '/pdf/' in url and not url.endswith('.pdf'):
                url = url + '.pdf'
        
        # Remove multiple slashes (except after protocol)
        url = re.sub(r'(?<!:)//+', '/', url)
        
        # Fix common issues
        url = url.replace('\\', '/')
        
        return url.strip()
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Validate if URL is legitimate
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid
        """
        # Check against exclude patterns
        for pattern in self.exclude_patterns:
            if pattern.search(url):
                return False
        
        # Must have protocol
        if not re.match(r'^[a-z]+://', url, re.IGNORECASE):
            return False
        
        # Try to parse URL
        try:
            result = urlparse(url)
            
            # Must have scheme and netloc
            if not all([result.scheme, result.netloc]):
                return False
            
            # Check for valid domain structure
            if '.' not in result.netloc and result.netloc != 'localhost':
                return False
            
            # Check for minimum length
            if len(url) < 10:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _extract_context(self, text: str, start: int, end: int, context_size: int = 100) -> str:
        """
        Extract context around URL
        
        Args:
            text: Full text
            start: Start position of URL
            end: End position of URL
            context_size: Characters to include before/after
            
        Returns:
            Context string
        """
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)
        
        context = text[context_start:context_end]
        
        # Clean up context
        context = context.replace('\n', ' ').replace('\r', ' ')
        context = re.sub(r'\s+', ' ', context)
        
        # Add ellipsis if truncated
        if context_start > 0:
            context = '...' + context
        if context_end < len(text):
            context = context + '...'
        
        return context.strip()
    
    def _calculate_url_confidence(self, url: str, context: str) -> float:
        """
        Calculate confidence score for URL
        
        Args:
            url: The URL
            context: Surrounding context
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.5  # Base confidence
        
        # Boost for complete protocol
        if url.startswith(('https://', 'http://')):
            confidence += 0.2
        
        # Boost for known domains
        known_domains = ['github.com', 'arxiv.org', 'doi.org', 'wikipedia.org', 
                        'google.com', 'stackoverflow.com', 'medium.com']
        if any(domain in url.lower() for domain in known_domains):
            confidence += 0.2
        
        # Boost for file extensions indicating documents
        doc_extensions = ['.pdf', '.html', '.htm', '.doc', '.docx', '.txt', '.md']
        if any(url.lower().endswith(ext) for ext in doc_extensions):
            confidence += 0.1
        
        # Context-based confidence
        positive_context = ['link', 'url', 'source', 'reference', 'article', 
                           'paper', 'document', 'website', 'page', 'voir', 'see']
        if any(word in context.lower() for word in positive_context):
            confidence += 0.1
        
        # Penalize suspicious patterns
        suspicious = ['spam', 'ad', 'click here', 'buy now', 'sale']
        if any(word in context.lower() for word in suspicious):
            confidence -= 0.3
        
        # Cap confidence
        return min(max(confidence, 0.0), 1.0)
    
    def _identify_service(self, url: str) -> Optional[str]:
        """
        Identify the service/platform from URL
        
        Args:
            url: The URL
            
        Returns:
            Service name or None
        """
        url_lower = url.lower()
        
        service_mappings = {
            'github.com': 'github',
            'gitlab.com': 'gitlab',
            'bitbucket.org': 'bitbucket',
            'arxiv.org': 'arxiv',
            'doi.org': 'doi',
            'pubmed': 'pubmed',
            'youtube.com': 'youtube',
            'youtu.be': 'youtube',
            'twitter.com': 'twitter',
            'x.com': 'twitter',
            'linkedin.com': 'linkedin',
            'reddit.com': 'reddit',
            'stackoverflow.com': 'stackoverflow',
            'wikipedia.org': 'wikipedia',
            'medium.com': 'medium',
            'nature.com': 'nature',
            'science.org': 'science',
            'springer.com': 'springer',
            'elsevier.com': 'elsevier',
            'ieee.org': 'ieee',
            'acm.org': 'acm',
        }
        
        for domain, service in service_mappings.items():
            if domain in url_lower:
                return service
        
        return None
    
    def deduplicate_urls(self, urls: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Remove duplicate URLs, keeping the one with highest confidence
        
        Args:
            urls: List of URL dictionaries
            
        Returns:
            Deduplicated list
        """
        seen = {}
        
        for url_info in urls:
            url = url_info['url']
            
            # Normalize for comparison
            normalized = self._normalize_url_for_comparison(url)
            
            if normalized not in seen or url_info['confidence'] > seen[normalized]['confidence']:
                seen[normalized] = url_info
        
        return list(seen.values())
    
    def _normalize_url_for_comparison(self, url: str) -> str:
        """
        Normalize URL for deduplication comparison
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL
        """
        # Parse URL
        try:
            parsed = urlparse(url.lower())
            
            # Remove www prefix
            netloc = parsed.netloc
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            # Remove trailing slash from path
            path = parsed.path.rstrip('/')
            
            # Reconstruct normalized URL
            normalized = urlunparse((
                parsed.scheme,
                netloc,
                path,
                '',  # params
                parsed.query,
                ''   # fragment
            ))
            
            return normalized
            
        except Exception:
            return url.lower()
    
    def format_urls_for_output(self, urls: List[Dict[str, str]]) -> str:
        """
        Format URLs for display in output
        
        Args:
            urls: List of URL dictionaries
            
        Returns:
            Formatted string
        """
        if not urls:
            return ""
        
        output = "\n## 📎 Liens et références\n\n"
        
        # Group by service if available
        by_service = {}
        no_service = []
        
        for url_info in urls:
            service = url_info.get('service')
            if service:
                if service not in by_service:
                    by_service[service] = []
                by_service[service].append(url_info)
            else:
                no_service.append(url_info)
        
        # Format grouped URLs
        for service, service_urls in sorted(by_service.items()):
            output += f"### {service.title()}\n"
            for url_info in service_urls:
                url = url_info['url']
                # Prefer description over context
                description = url_info.get('description')
                if not description:
                    context = url_info.get('context', '')
                    # Truncate context if too long
                    if len(context) > 150:
                        context = context[:147] + '...'
                    description = context
                
                output += f"- [{url}]({url})"
                if description:
                    output += f" - {description}"
                output += "\n"
            output += "\n"
        
        # Format ungrouped URLs
        if no_service:
            output += "### Autres liens\n"
            for url_info in no_service:
                url = url_info['url']
                # Prefer description over context
                description = url_info.get('description')
                if not description:
                    context = url_info.get('context', '')
                    if len(context) > 150:
                        context = context[:147] + '...'
                    description = context
                
                output += f"- [{url}]({url})"
                if description:
                    output += f" - {description}"
                output += "\n"
        
        return output