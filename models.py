"""
Data models for SEBI circular reference extraction.

This module defines Pydantic models that ensure type safety and validation
for all data structures used in the extraction pipeline. These models match
the JSON schema specification from the implementation plan.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator


class DocumentType(str, Enum):
    """Types of regulatory documents that can be referenced."""
    SEBI_CIRCULAR = "SEBI_CIRCULAR"
    ACT = "ACT"
    REGULATION = "REGULATION"
    GUIDELINE = "GUIDELINE"
    NOTIFICATION = "NOTIFICATION"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    """How the source circular relates to the referenced document."""
    SUPERSEDES = "SUPERSEDES"  # Replaces the referenced document entirely
    AMENDS = "AMENDS"  # Modifies specific parts of the referenced document
    REPEALS = "REPEALS"  # Cancels the referenced document
    REFERS_TO = "REFERS_TO"  # General reference without modification
    CLARIFIES = "CLARIFIES"  # Provides additional explanation
    DERIVES_FROM = "DERIVES_FROM"  # Based on/authorized by the referenced document


class ExtractionSource(str, Enum):
    """Which processing track found this reference."""
    BOTH = "BOTH"  # Found by both Track A and Track B
    TRACK_A = "TRACK_A"  # Found only by global context analysis
    TRACK_B = "TRACK_B"  # Found only by agentic search


class ValidationStatus(str, Enum):
    """Overall processing completion status."""
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SourceDocument(BaseModel):
    """Metadata about the source SEBI circular being processed."""
    
    filename: str = Field(..., description="Original PDF filename")
    circular_title: str = Field(..., description="Official title of the circular")
    sebi_reference_number: str = Field(..., description="SEBI reference number (e.g., SEBI/HO/MIRSD/2024/120)")
    date_issued: Optional[str] = Field(None, description="Date circular was issued (YYYY-MM-DD)")
    total_pages: int = Field(..., description="Total number of pages in the PDF")
    processing_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="When pipeline processed this document (UTC)"
    )


class Reference(BaseModel):
    """A single extracted reference to another regulatory document."""
    
    reference_id: str = Field(..., description="Unique identifier (e.g., REF001)")
    referenced_document_title: str = Field(..., description="Title of the referenced document")
    referenced_sebi_number: Optional[str] = Field(None, description="Reference number of the cited document")
    referenced_date: Optional[str] = Field(None, description="Date of referenced document (YYYY-MM-DD)")
    document_type: DocumentType = Field(..., description="Type of referenced document")
    relationship_type: RelationshipType = Field(..., description="How documents are related")
    page_numbers: List[int] = Field(..., description="Pages where this reference appears")
    exact_citation_text: str = Field(..., description="Verbatim quote of the citation")
    context_paragraph: str = Field(..., description="Full paragraph containing the reference")
    section_location: str = Field(..., description="Section where reference appears")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Reliability score (0.0-1.0)")
    extraction_source: ExtractionSource = Field(..., description="Which track found this")
    
    @field_validator('page_numbers')
    @classmethod
    def page_numbers_must_be_positive(cls, v):
        """Ensure all page numbers are positive integers."""
        if any(page <= 0 for page in v):
            raise ValueError("Page numbers must be positive integers")
        return v


class SummaryStatistics(BaseModel):
    """Aggregated statistics about extracted references."""
    
    total_references_found: int = Field(..., description="Total unique references extracted")
    by_document_type: Dict[str, int] = Field(..., description="Count by document type")
    by_relationship_type: Dict[str, int] = Field(..., description="Count by relationship type")
    by_confidence_level: Dict[str, int] = Field(
        ...,
        description="Count by confidence: high (>0.9), medium (0.7-0.9), low (<0.7)"
    )
    by_extraction_source: Dict[str, int] = Field(..., description="Count by extraction source")
    page_coverage: Dict[str, Any] = Field(..., description="Pages with references and coverage stats")


class ProcessingMetadata(BaseModel):
    """Metadata about pipeline execution."""
    
    pipeline_version: str = Field(default="1.0.0", description="Pipeline version")
    models_used: Dict[str, str] = Field(..., description="AI models used in each track")
    processing_time_seconds: int = Field(..., description="Total execution time")
    track_a_references_found: int = Field(..., description="Count before deduplication from Track A")
    track_b_references_found: int = Field(..., description="Count before deduplication from Track B")
    merged_count: int = Field(..., description="Final count after merging")
    duplicates_removed: int = Field(..., description="Number of duplicates eliminated")
    conflicts_resolved: int = Field(..., description="Number of disagreements resolved")
    validation_status: ValidationStatus = Field(..., description="Overall processing status")
    warnings: List[str] = Field(default_factory=list, description="Issues flagged for human review")


class FinalOutput(BaseModel):
    """Complete output schema for the extraction pipeline."""
    
    source_document: SourceDocument
    references: List[Reference]
    summary_statistics: SummaryStatistics
    processing_metadata: ProcessingMetadata
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "source_document": {
                    "filename": "sebi_circular_2024_120.pdf",
                    "circular_title": "Master Circular on Portfolio Management Services",
                    "sebi_reference_number": "SEBI/HO/MIRSD/2024/120",
                    "date_issued": "2024-09-15",
                    "total_pages": 47,
                    "processing_timestamp": "2026-01-21T06:30:00Z"
                },
                "references": [],
                "summary_statistics": {},
                "processing_metadata": {}
            }
        }
