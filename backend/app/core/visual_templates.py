"""
Visual Templates for Meta Chat

This module contains HTML/CSS/JS templates for generating visual responses.
"""

from typing import Dict, Any


class VisualTemplates:
    """Collection of visual response templates"""
    
    @staticmethod
    def get_base_template(title: str, content: str, theme: str = "light") -> str:
        """Base HTML template with theme support"""
        bg_color = "#ffffff" if theme == "light" else "#1a1a1a"
        text_color = "#333333" if theme == "light" else "#ffffff"
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: {bg_color};
            color: {text_color};
            padding: 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 800px;
            animation: fadeIn 0.5s ease-in;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>"""

    @staticmethod
    def weather_widget(data: Dict[str, Any], theme: str = "light") -> str:
        """Weather widget template"""
        # Check if data contains error
        if 'error' in data:
            return VisualTemplates.get_base_template(
                "Error", 
                f'<div style="text-align: center; padding: 40px;"><h2>Error loading weather data</h2><p>{data.get("error")}</p></div>', 
                theme
            )
        
        location = data.get('location', 'Unknown')
        temp = data.get('temperature', 'N/A')
        condition = data.get('condition', 'Unknown')
        
        # Map conditions to emojis
        weather_icons = {
            'sunny': '☀️',
            'clear': '☀️',
            'partly-cloudy': '⛅',
            'partly cloudy': '⛅',
            'cloudy': '☁️',
            'mostly-cloudy': '☁️',
            'overcast': '☁️',
            'rain': '🌧️',
            'light-rain': '🌦️',
            'light rain': '🌦️',
            'heavy-rain': '⛈️',
            'snow': '❄️',
            'thunderstorm': '⛈️',
            'fog': '🌫️',
            'wind': '💨️'
        }
        
        icon_key = data.get('icon', condition).lower()
        icon = weather_icons.get(icon_key, weather_icons.get(condition.lower(), '🌤️'))
        forecast = data.get('forecast', [])
        
        forecast_html = ""
        for day in forecast[:5]:
            forecast_html += f"""
            <div class="forecast-day">
                <div class="day-name">{day.get('day', 'Day')}</div>
                <div class="day-icon">{day.get('icon', '☁️')}</div>
                <div class="day-temp">{day.get('temp', 'N/A')}°</div>
            </div>
            """
        
        content = f"""
        <div class="weather-widget">
            <h1 class="location">{location}</h1>
            <div class="current">
                <div class="temp-display">
                    <span class="temperature">{temp}°</span>
                    <span class="condition">{condition}</span>
                </div>
                <div class="weather-icon">{icon}</div>
            </div>
            <div class="forecast">
                {forecast_html}
            </div>
        </div>
        <style>
            .weather-widget {{
                text-align: center;
                padding: 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 20px;
                color: white;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            .location {{
                font-size: 2em;
                margin-bottom: 20px;
                font-weight: 300;
            }}
            .current {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 40px;
                margin-bottom: 40px;
            }}
            .temperature {{
                font-size: 4em;
                font-weight: 200;
            }}
            .condition {{
                display: block;
                font-size: 1.2em;
                margin-top: 10px;
            }}
            .weather-icon {{
                font-size: 5em;
                animation: float 3s ease-in-out infinite;
            }}
            .forecast {{
                display: flex;
                justify-content: space-around;
                gap: 20px;
                margin-top: 30px;
                padding-top: 30px;
                border-top: 1px solid rgba(255,255,255,0.3);
            }}
            .forecast-day {{
                text-align: center;
            }}
            .day-name {{
                font-size: 0.9em;
                opacity: 0.8;
                margin-bottom: 10px;
            }}
            .day-icon {{
                font-size: 2em;
                margin: 10px 0;
            }}
            .day-temp {{
                font-size: 1.1em;
            }}
            @keyframes float {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-10px); }}
            }}
        </style>
        """
        
        return VisualTemplates.get_base_template(f"Weather - {location}", content, theme)

    @staticmethod
    def math_visualizer(data: Dict[str, Any], theme: str = "light") -> str:
        """Math visualization template"""
        expression = data.get('expression', '')
        result = data.get('result', '')
        steps = data.get('steps', [])
        
        steps_html = ""
        for i, step in enumerate(steps):
            steps_html += f"""
            <div class="step" style="animation-delay: {i * 0.2}s">
                <span class="step-number">Step {i + 1}</span>
                <span class="step-content">{step}</span>
            </div>
            """
        
        content = f"""
        <div class="math-viz">
            <h1 class="expression">{expression}</h1>
            <div class="steps-container">
                {steps_html}
            </div>
            <div class="result">
                <span class="equals">=</span>
                <span class="result-value">{result}</span>
            </div>
        </div>
        <style>
            .math-viz {{
                text-align: center;
                padding: 40px;
            }}
            .expression {{
                font-size: 2.5em;
                margin-bottom: 40px;
                color: #667eea;
                font-weight: 300;
            }}
            .steps-container {{
                margin: 30px 0;
            }}
            .step {{
                background: #f7fafc;
                padding: 15px 25px;
                margin: 10px 0;
                border-radius: 10px;
                display: inline-block;
                animation: slideIn 0.5s ease-out forwards;
                opacity: 0;
            }}
            .step-number {{
                color: #667eea;
                font-weight: 600;
                margin-right: 15px;
            }}
            .result {{
                font-size: 3em;
                margin-top: 40px;
                animation: bounceIn 0.8s ease-out;
            }}
            .equals {{
                color: #667eea;
                margin-right: 20px;
            }}
            .result-value {{
                color: #48bb78;
                font-weight: 600;
            }}
            @keyframes slideIn {{
                from {{ opacity: 0; transform: translateX(-30px); }}
                to {{ opacity: 1; transform: translateX(0); }}
            }}
            @keyframes bounceIn {{
                0% {{ transform: scale(0); }}
                50% {{ transform: scale(1.2); }}
                100% {{ transform: scale(1); }}
            }}
        </style>
        <script>
            // Add interactive effects
            document.querySelectorAll('.step').forEach((step, index) => {{
                step.addEventListener('click', () => {{
                    step.style.transform = 'scale(1.05)';
                    setTimeout(() => {{
                        step.style.transform = 'scale(1)';
                    }}, 200);
                }});
            }});
        </script>
        """
        
        return VisualTemplates.get_base_template("Math Visualization", content, theme)

    @staticmethod
    def data_chart(data: Dict[str, Any], theme: str = "light") -> str:
        """Data chart template using Chart.js"""
        chart_type = data.get('type', 'line')
        chart_data = data.get('data', {})
        title = data.get('title', 'Data Visualization')
        
        content = f"""
        <div class="chart-container">
            <h1>{title}</h1>
            <canvas id="myChart"></canvas>
        </div>
        <style>
            .chart-container {{
                padding: 30px;
                background: white;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            }}
            h1 {{
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }}
            canvas {{
                max-height: 400px;
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const ctx = document.getElementById('myChart').getContext('2d');
            const myChart = new Chart(ctx, {{
                type: '{chart_type}',
                data: {json.dumps(chart_data)},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    animation: {{
                        duration: 2000,
                        easing: 'easeInOutQuart'
                    }}
                }}
            }});
        </script>
        """
        
        return VisualTemplates.get_base_template(title, content, theme)

    @staticmethod
    def interactive_tutorial(data: Dict[str, Any], theme: str = "light") -> str:
        """Interactive tutorial template"""
        title = data.get('title', 'Tutorial')
        sections = data.get('sections', [])
        
        sections_html = ""
        for i, section in enumerate(sections):
            sections_html += f"""
            <div class="section" id="section-{i}">
                <h2>{section.get('title', f'Section {i+1}')}</h2>
                <div class="content">{section.get('content', '')}</div>
                {f'<div class="interactive">{section.get("interactive", "")}</div>' if section.get('interactive') else ''}
            </div>
            """
        
        content = f"""
        <div class="tutorial">
            <h1 class="main-title">{title}</h1>
            <div class="progress-bar">
                <div class="progress" id="progress"></div>
            </div>
            <div class="sections">
                {sections_html}
            </div>
            <div class="navigation">
                <button id="prev" onclick="navigate(-1)">Previous</button>
                <span id="current">1 / {len(sections)}</span>
                <button id="next" onclick="navigate(1)">Next</button>
            </div>
        </div>
        <style>
            .tutorial {{
                max-width: 800px;
                margin: 0 auto;
            }}
            .main-title {{
                text-align: center;
                margin-bottom: 30px;
                color: #667eea;
            }}
            .progress-bar {{
                height: 4px;
                background: #e2e8f0;
                border-radius: 2px;
                margin-bottom: 40px;
                overflow: hidden;
            }}
            .progress {{
                height: 100%;
                background: #667eea;
                width: 0;
                transition: width 0.3s ease;
            }}
            .section {{
                display: none;
                animation: fadeIn 0.5s ease;
            }}
            .section.active {{
                display: block;
            }}
            .section h2 {{
                color: #667eea;
                margin-bottom: 20px;
            }}
            .content {{
                line-height: 1.8;
                margin-bottom: 30px;
            }}
            .interactive {{
                background: #f7fafc;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}
            .navigation {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 40px;
            }}
            button {{
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s ease;
            }}
            button:hover {{
                background: #5a67d8;
                transform: translateY(-2px);
            }}
            button:disabled {{
                opacity: 0.5;
                cursor: not-allowed;
            }}
        </style>
        <script>
            let currentSection = 0;
            const totalSections = {len(sections)};
            
            function showSection(index) {{
                document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
                document.getElementById('section-' + index).classList.add('active');
                document.getElementById('current').textContent = (index + 1) + ' / ' + totalSections;
                document.getElementById('progress').style.width = ((index + 1) / totalSections * 100) + '%';
                
                document.getElementById('prev').disabled = index === 0;
                document.getElementById('next').disabled = index === totalSections - 1;
            }}
            
            function navigate(direction) {{
                currentSection = Math.max(0, Math.min(totalSections - 1, currentSection + direction));
                showSection(currentSection);
            }}
            
            // Initialize
            showSection(0);
        </script>
        """
        
        return VisualTemplates.get_base_template(title, content, theme)

    @staticmethod
    def code_playground(data: Dict[str, Any], theme: str = "light") -> str:
        """Code playground template"""
        code = data.get('code', '')
        language = data.get('language', 'javascript')
        title = data.get('title', 'Code Playground')
        
        content = f"""
        <div class="playground">
            <h1>{title}</h1>
            <div class="editor-container">
                <div class="editor-header">
                    <span class="language">{language}</span>
                    <button onclick="runCode()">Run Code</button>
                </div>
                <textarea id="code-editor" class="editor">{code}</textarea>
            </div>
            <div class="output-container">
                <div class="output-header">Output</div>
                <div id="output" class="output"></div>
            </div>
        </div>
        <style>
            .playground {{
                max-width: 900px;
                margin: 0 auto;
            }}
            h1 {{
                text-align: center;
                color: #667eea;
                margin-bottom: 30px;
            }}
            .editor-container, .output-container {{
                background: #2d3748;
                border-radius: 10px;
                overflow: hidden;
                margin-bottom: 20px;
            }}
            .editor-header, .output-header {{
                background: #1a202c;
                color: white;
                padding: 10px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .language {{
                color: #48bb78;
                font-family: monospace;
            }}
            .editor {{
                width: 100%;
                min-height: 300px;
                background: #2d3748;
                color: #fff;
                border: none;
                padding: 20px;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 14px;
                line-height: 1.5;
                resize: vertical;
            }}
            .output {{
                min-height: 150px;
                padding: 20px;
                font-family: monospace;
                color: #48bb78;
                white-space: pre-wrap;
            }}
            button {{
                background: #48bb78;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }}
            button:hover {{
                background: #38a169;
            }}
        </style>
        <script>
            function runCode() {{
                const code = document.getElementById('code-editor').value;
                const output = document.getElementById('output');
                
                try {{
                    // Capture console.log
                    const logs = [];
                    const originalLog = console.log;
                    console.log = function(...args) {{
                        logs.push(args.join(' '));
                    }};
                    
                    // Execute code
                    eval(code);
                    
                    // Restore console.log
                    console.log = originalLog;
                    
                    // Display output
                    output.textContent = logs.join('\\n') || 'Code executed successfully!';
                    output.style.color = '#48bb78';
                }} catch (error) {{
                    output.textContent = 'Error: ' + error.message;
                    output.style.color = '#f56565';
                }}
            }}
            
            // Syntax highlighting (basic)
            document.getElementById('code-editor').addEventListener('input', function(e) {{
                // Basic syntax highlighting could be added here
            }});
        </script>
        """
        
        return VisualTemplates.get_base_template(title, content, theme)

    @staticmethod
    def custom_html(data: Dict[str, Any], theme: str = "light") -> str:
        """Custom HTML template for advanced visualizations"""
        html = data.get('html', '')
        css = data.get('css', '')
        js = data.get('js', '')
        title = data.get('title', 'Custom Visualization')
        
        content = f"""
        {html}
        <style>
            {css}
        </style>
        <script>
            {js}
        </script>
        """
        
        return VisualTemplates.get_base_template(title, content, theme)


import json  # Add this import at the top of the file