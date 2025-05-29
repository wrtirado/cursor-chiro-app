"""
Branding Schema Definitions

This module contains Pydantic models for branding operations,
including custom logos and color schemes for offices.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
import json


class BrandingColors(BaseModel):
    """Structured color scheme for branding"""

    primary: Optional[str] = Field(None, description="Primary brand color (hex)")
    secondary: Optional[str] = Field(None, description="Secondary brand color (hex)")
    accent: Optional[str] = Field(None, description="Accent color (hex)")
    background: Optional[str] = Field(None, description="Background color (hex)")
    text: Optional[str] = Field(None, description="Text color (hex)")

    @validator("primary", "secondary", "accent", "background", "text")
    def validate_hex_color(cls, v):
        if v is not None and not (v.startswith("#") and len(v) == 7):
            try:
                # Allow shorthand hex colors like #fff
                if v.startswith("#") and len(v) == 4:
                    return v  # Valid shorthand hex
                # Validate full hex color
                int(v[1:], 16)  # This will raise ValueError if not valid hex
                return v
            except (ValueError, IndexError):
                raise ValueError(
                    "Color must be a valid hex color (e.g., #FF5733 or #fff)"
                )
        return v


class BrandingBase(BaseModel):
    """Base branding schema with common attributes"""

    logo_url: Optional[HttpUrl] = Field(
        None, description="URL to the custom logo image"
    )
    colors: Optional[Dict[str, Any]] = Field(
        None, description="Custom color scheme as JSON"
    )

    @validator("colors")
    def validate_colors_json(cls, v):
        if v is not None:
            # Ensure it's a valid dict that can be serialized to JSON
            if not isinstance(v, dict):
                raise ValueError("Colors must be a JSON object")
            try:
                json.dumps(v)  # Test if it's JSON serializable
            except (TypeError, ValueError):
                raise ValueError("Colors must be JSON serializable")
        return v


class BrandingCreate(BrandingBase):
    """Schema for creating branding"""

    office_id: int = Field(..., description="Office ID this branding belongs to")


class BrandingUpdate(BaseModel):
    """Schema for updating branding (all fields optional)"""

    logo_url: Optional[HttpUrl] = Field(
        None, description="URL to the custom logo image"
    )
    colors: Optional[Dict[str, Any]] = Field(
        None, description="Custom color scheme as JSON"
    )

    @validator("colors")
    def validate_colors_json(cls, v):
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("Colors must be a JSON object")
            try:
                json.dumps(v)
            except (TypeError, ValueError):
                raise ValueError("Colors must be JSON serializable")
        return v


class BrandingResponse(BrandingBase):
    """Schema for branding responses"""

    branding_id: int = Field(..., description="Unique branding ID")
    office_id: int = Field(..., description="Office ID this branding belongs to")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class BrandingResponseWithDefaults(BrandingResponse):
    """Schema for branding responses with default fallbacks applied"""

    has_custom_logo: bool = Field(..., description="Whether a custom logo is set")
    has_custom_colors: bool = Field(..., description="Whether custom colors are set")
    effective_colors: Dict[str, Any] = Field(
        ..., description="Final colors including defaults"
    )


class DefaultBrandingConfig(BaseModel):
    """Schema for default branding configuration"""

    default_logo_url: Optional[HttpUrl] = Field(None, description="Default logo URL")
    default_colors: Dict[str, Any] = Field(..., description="Default color scheme")

    class Config:
        from_attributes = True
