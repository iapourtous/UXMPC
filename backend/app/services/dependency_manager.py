"""
Dynamic dependency management for UXMCP services
"""
import subprocess
import sys
import os
import json
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DependencyManager:
    """Manages dynamic Python package installation and persistence"""
    
    def __init__(self):
        self.dynamic_requirements_path = Path("/app/dynamic_requirements.txt")
        self.installed_packages_cache = set()
        self._load_installed_packages()
    
    def _load_installed_packages(self):
        """Load list of already installed dynamic packages"""
        if self.dynamic_requirements_path.exists():
            with open(self.dynamic_requirements_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        package_name = line.split('==')[0].split('>=')[0].split('<=')[0]
                        self.installed_packages_cache.add(package_name.lower())
    
    def _save_to_requirements(self, package: str, version: Optional[str] = None):
        """Add package to dynamic requirements file"""
        package_spec = f"{package}=={version}" if version else package
        
        # Check if already in file
        existing_lines = []
        if self.dynamic_requirements_path.exists():
            with open(self.dynamic_requirements_path, 'r') as f:
                existing_lines = f.readlines()
        
        # Check if package already exists
        package_exists = False
        for i, line in enumerate(existing_lines):
            if line.strip() and not line.strip().startswith('#'):
                existing_package = line.strip().split('==')[0].split('>=')[0].split('<=')[0]
                if existing_package.lower() == package.lower():
                    existing_lines[i] = f"{package_spec}\n"
                    package_exists = True
                    break
        
        # Add new package if not exists
        if not package_exists:
            existing_lines.append(f"{package_spec}\n")
        
        # Write back to file
        with open(self.dynamic_requirements_path, 'w') as f:
            if not existing_lines or not any(line.startswith('#') for line in existing_lines):
                f.write("# Dynamic dependencies installed by UXMCP services\n")
                f.write("# This file is automatically managed by the system\n")
            f.writelines(existing_lines)
    
    def install_package(self, package: str, version: Optional[str] = None) -> Dict[str, any]:
        """
        Install a Python package dynamically
        
        Args:
            package: Package name to install
            version: Optional specific version
            
        Returns:
            Dict with success status and message
        """
        try:
            # Check if already installed
            package_lower = package.lower()
            if package_lower in self.installed_packages_cache:
                return {
                    "success": True,
                    "message": f"Package {package} is already installed",
                    "already_installed": True
                }
            
            # Construct pip command
            package_spec = f"{package}=={version}" if version else package
            cmd = [sys.executable, "-m", "pip", "install", package_spec]
            
            logger.info(f"Installing package: {package_spec}")
            
            # Run pip install
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Save to requirements file
                self._save_to_requirements(package, version)
                self.installed_packages_cache.add(package_lower)
                
                return {
                    "success": True,
                    "message": f"Successfully installed {package_spec}",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to install {package_spec}",
                    "error": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": f"Installation of {package} timed out after 5 minutes"
            }
        except Exception as e:
            logger.error(f"Error installing package {package}: {str(e)}")
            return {
                "success": False,
                "message": f"Unexpected error installing {package}: {str(e)}"
            }
    
    def get_installed_packages(self) -> List[str]:
        """Get list of dynamically installed packages"""
        packages = []
        if self.dynamic_requirements_path.exists():
            with open(self.dynamic_requirements_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        packages.append(line)
        return packages
    
    def check_package_installed(self, package: str) -> bool:
        """Check if a package is installed"""
        try:
            __import__(package)
            return True
        except ImportError:
            # Try common import name variations
            common_mappings = {
                'pillow': 'PIL',
                'beautifulsoup4': 'bs4',
                'opencv-python': 'cv2',
                'scikit-learn': 'sklearn',
                'python-dateutil': 'dateutil'
            }
            
            if package.lower() in common_mappings:
                try:
                    __import__(common_mappings[package.lower()])
                    return True
                except ImportError:
                    pass
            
            return False
    
    def install_from_requirements(self) -> Dict[str, any]:
        """Install all packages from dynamic requirements file"""
        if not self.dynamic_requirements_path.exists():
            return {
                "success": True,
                "message": "No dynamic requirements file found"
            }
        
        try:
            cmd = [
                sys.executable, "-m", "pip", "install", 
                "-r", str(self.dynamic_requirements_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                # Reload installed packages cache
                self._load_installed_packages()
                return {
                    "success": True,
                    "message": "Successfully installed all dynamic requirements",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to install some requirements",
                    "error": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Installation timed out after 10 minutes"
            }
        except Exception as e:
            logger.error(f"Error installing from requirements: {str(e)}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }

# Global instance
dependency_manager = DependencyManager()