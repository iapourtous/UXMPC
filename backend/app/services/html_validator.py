"""
HTML Validator Service

Simple validation service using Playwright to test generated HTML/JS
"""

import logging
from typing import Dict, List
from playwright.async_api import async_playwright
import asyncio
import re

logger = logging.getLogger(__name__)


class HTMLValidator:
    """Validates HTML content using a headless browser"""
    
    async def test_html(self, html_content: str) -> Dict[str, any]:
        """
        Test HTML content in a browser and return validation results
        
        Args:
            html_content: The HTML string to validate
            
        Returns:
            Dictionary with 'success' boolean and 'errors' list
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            try:
                context = await browser.new_context()
                page = await context.new_page()
                
                # Collect errors
                console_errors = []
                page_errors = []
                
                # Listen for console errors
                page.on("console", lambda msg: console_errors.append({
                    'type': 'console_error',
                    'text': msg.text
                }) if msg.type == "error" else None)
                
                # Listen for page errors
                page.on("pageerror", lambda error: page_errors.append({
                    'type': 'page_error',
                    'text': str(error)
                }))
                
                # Load the HTML content
                await page.set_content(html_content)
                
                # Wait a bit for JavaScript to execute
                await page.wait_for_timeout(2000)
                
                # Run validation tests
                validation_results = await page.evaluate('''() => {
                    const errors = [];
                    
                    // Check for duplicate function declarations
                    const scriptContent = Array.from(document.scripts)
                        .map(s => s.innerHTML)
                        .join('\\n');
                    
                    const functionPattern = /function\\s+(\\w+)\\s*\\(/g;
                    const functions = {};
                    let match;
                    
                    while ((match = functionPattern.exec(scriptContent)) !== null) {
                        const funcName = match[1];
                        functions[funcName] = (functions[funcName] || 0) + 1;
                    }
                    
                    for (const [name, count] of Object.entries(functions)) {
                        if (count > 1) {
                            errors.push({
                                type: 'duplicate_function',
                                text: `Function '${name}' is declared ${count} times`
                            });
                        }
                    }
                    
                    // For games: check if canvas exists
                    if (typeof p5 !== 'undefined' || scriptContent.includes('createCanvas')) {
                        const canvas = document.querySelector('canvas');
                        if (!canvas) {
                            errors.push({
                                type: 'missing_canvas',
                                text: 'Game uses p5.js but no canvas element found'
                            });
                        }
                        
                        // Check essential p5.js functions
                        if (typeof setup !== 'function') {
                            errors.push({
                                type: 'missing_function',
                                text: 'p5.js game missing setup() function'
                            });
                        }
                        if (typeof draw !== 'function') {
                            errors.push({
                                type: 'missing_function', 
                                text: 'p5.js game missing draw() function'
                            });
                        }
                    }
                    
                    // Check for Snake-specific issues
                    if (typeof snake !== 'undefined' && snake) {
                        try {
                            if (snake.xdir === 0 && snake.ydir === 0) {
                                errors.push({
                                    type: 'game_logic',
                                    text: 'Snake has no initial direction (xdir=0, ydir=0)'
                                });
                            }
                        } catch (e) {
                            // Snake might not be initialized yet
                        }
                    }
                    
                    return errors;
                }''')
                
                # Combine all errors
                all_errors = [
                    *console_errors,
                    *page_errors,
                    *validation_results
                ]
                
                # Log errors for debugging
                if all_errors:
                    logger.info(f"HTML validation found {len(all_errors)} errors")
                    for error in all_errors[:5]:  # Log first 5 errors
                        logger.info(f"  - {error['type']}: {error['text']}")
                
                return {
                    'success': len(all_errors) == 0,
                    'errors': all_errors
                }
                
            finally:
                await browser.close()
    
    def format_errors_for_llm(self, errors: List[Dict]) -> str:
        """
        Format validation errors into a clear message for the LLM
        
        Args:
            errors: List of error dictionaries
            
        Returns:
            Formatted error message
        """
        if not errors:
            return ""
        
        error_messages = []
        
        # Group errors by type
        error_groups = {}
        for error in errors:
            error_type = error.get('type', 'unknown')
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(error['text'])
        
        # Format each group
        for error_type, messages in error_groups.items():
            if error_type == 'duplicate_function':
                error_messages.append("DUPLICATE FUNCTIONS:")
                for msg in messages:
                    error_messages.append(f"  - {msg}")
            elif error_type == 'console_error':
                error_messages.append("JAVASCRIPT ERRORS:")
                for msg in messages:
                    error_messages.append(f"  - {msg}")
            elif error_type == 'game_logic':
                error_messages.append("GAME LOGIC ISSUES:")
                for msg in messages:
                    error_messages.append(f"  - {msg}")
            else:
                error_messages.append(f"{error_type.upper()}:")
                for msg in messages:
                    error_messages.append(f"  - {msg}")
        
        return "\n".join(error_messages)


# Singleton instance
html_validator = HTMLValidator()