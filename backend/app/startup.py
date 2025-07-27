"""
Startup script to initialize dynamic dependencies
"""
import logging
from app.services.dependency_manager import dependency_manager

logger = logging.getLogger(__name__)

def initialize_dynamic_dependencies():
    """Install all dynamic dependencies on startup"""
    logger.info("Initializing dynamic dependencies...")
    
    result = dependency_manager.install_from_requirements()
    
    if result["success"]:
        logger.info(result["message"])
        packages = dependency_manager.get_installed_packages()
        if packages:
            logger.info(f"Loaded {len(packages)} dynamic packages: {', '.join(packages)}")
    else:
        logger.error(f"Failed to initialize dependencies: {result['message']}")
        if "error" in result:
            logger.error(f"Error details: {result['error']}")

# Run on import
if __name__ != "__main__":
    initialize_dynamic_dependencies()