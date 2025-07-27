"""
API endpoints for managing dynamic dependencies
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.dependency_manager import dependency_manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class InstallPackageRequest(BaseModel):
    package: str
    version: Optional[str] = None

class PackageResponse(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    already_installed: Optional[bool] = None

class PackageListResponse(BaseModel):
    packages: List[str]
    count: int

@router.post("/install", response_model=PackageResponse)
async def install_package(request: InstallPackageRequest):
    """Install a Python package dynamically"""
    try:
        result = dependency_manager.install_package(request.package, request.version)
        return PackageResponse(**result)
    except Exception as e:
        logger.error(f"Error installing package {request.package}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=PackageListResponse)
async def list_packages():
    """List all dynamically installed packages"""
    try:
        packages = dependency_manager.get_installed_packages()
        return PackageListResponse(
            packages=packages,
            count=len(packages)
        )
    except Exception as e:
        logger.error(f"Error listing packages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check/{package}")
async def check_package(package: str):
    """Check if a package is installed"""
    try:
        is_installed = dependency_manager.check_package_installed(package)
        return {
            "package": package,
            "installed": is_installed
        }
    except Exception as e:
        logger.error(f"Error checking package {package}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh")
async def refresh_dependencies():
    """Reinstall all dependencies from dynamic requirements file"""
    try:
        result = dependency_manager.install_from_requirements()
        return PackageResponse(**result)
    except Exception as e:
        logger.error(f"Error refreshing dependencies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))