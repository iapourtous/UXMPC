#!/usr/bin/env python3
"""
Check the status of prompt centralization in the UXMCP codebase.
"""

import os
import re
from pathlib import Path

def find_hardcoded_prompts(directory):
    """Find hardcoded prompts in Python files."""
    hardcoded_prompts = []
    
    # Patterns that indicate a hardcoded prompt
    patterns = [
        r'prompt\s*=\s*f?"""[\s\S]+?"""',
        r'prompt\s*=\s*f?"[^"]{100,}"',  # Long single line strings
        r'prompt\s*=\s*f?\'\'\'[\s\S]+?\'\'\'',
    ]
    
    for root, dirs, files in os.walk(directory):
        # Skip prompts directory
        if 'prompts' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.MULTILINE)
                        for match in matches:
                            # Check if it's using load_prompt
                            if 'load_prompt' not in match.group(0):
                                # Get line number
                                line_num = content[:match.start()].count('\n') + 1
                                hardcoded_prompts.append({
                                    'file': filepath,
                                    'line': line_num,
                                    'preview': match.group(0)[:100] + '...' if len(match.group(0)) > 100 else match.group(0)
                                })
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return hardcoded_prompts

def check_load_prompt_usage(directory):
    """Check files using load_prompt."""
    using_load_prompt = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    if 'load_prompt' in content:
                        # Count occurrences
                        count = content.count('load_prompt(')
                        using_load_prompt.append({
                            'file': filepath,
                            'count': count
                        })
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return using_load_prompt

def list_prompt_files(prompts_dir):
    """List all prompt files."""
    prompt_files = []
    
    if os.path.exists(prompts_dir):
        for root, dirs, files in os.walk(prompts_dir):
            for file in files:
                if file.endswith('.txt'):
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath, prompts_dir)
                    prompt_files.append(relative_path)
    
    return sorted(prompt_files)

def main():
    backend_dir = '/home/dess4ever/workspace/UXMCP/backend'
    prompts_dir = os.path.join(backend_dir, 'app', 'prompts')
    
    print("🔍 UXMCP Prompt Centralization Status Check")
    print("=" * 60)
    
    # Check for centralized prompts
    print("\n📁 Centralized Prompt Files:")
    prompt_files = list_prompt_files(prompts_dir)
    for pf in prompt_files:
        print(f"  ✅ {pf}")
    print(f"\nTotal: {len(prompt_files)} prompt files")
    
    # Check for files using load_prompt
    print("\n📄 Files Using load_prompt():")
    using_load_prompt = check_load_prompt_usage(backend_dir)
    for item in using_load_prompt:
        print(f"  ✅ {item['file']} ({item['count']} calls)")
    print(f"\nTotal: {len(using_load_prompt)} files")
    
    # Check for remaining hardcoded prompts
    print("\n⚠️  Remaining Hardcoded Prompts:")
    hardcoded = find_hardcoded_prompts(backend_dir)
    
    if hardcoded:
        for item in hardcoded:
            print(f"  ❌ {item['file']}:{item['line']}")
            print(f"     Preview: {item['preview']}")
    else:
        print("  🎉 No hardcoded prompts found!")
    
    print(f"\nTotal: {len(hardcoded)} hardcoded prompts remaining")
    
    # Summary
    print("\n📊 Summary:")
    print(f"  - Prompt files created: {len(prompt_files)}")
    print(f"  - Files using load_prompt: {len(using_load_prompt)}")
    print(f"  - Hardcoded prompts remaining: {len(hardcoded)}")
    
    if len(hardcoded) == 0:
        print("\n✅ All prompts have been centralized!")
    else:
        print(f"\n⏳ {len(hardcoded)} prompts still need to be centralized.")

if __name__ == "__main__":
    main()