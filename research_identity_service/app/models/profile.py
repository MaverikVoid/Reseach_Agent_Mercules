from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

class BasicInformation(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    scholar_url: Optional[str] = None

class EducationEntry(BaseModel):
    degree: str
    institution: str
    department: Optional[str] = None
    graduation_year: Optional[str] = None
    thesis_title: Optional[str] = None
    advisors: List[str] = Field(default_factory=list)

class CurrentPosition(BaseModel):
    title: str
    organization: str
    department: Optional[str] = None
    start_date: Optional[str] = None

class TechnicalSkills(BaseModel):
    programming_languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    libraries: List[str] = Field(default_factory=list)
    mathematics: List[str] = Field(default_factory=list)
    scientific_domains: List[str] = Field(default_factory=list)

class ProjectEntry(BaseModel):
    name: str
    description: str
    role: Optional[str] = None
    technologies_used: List[str] = Field(default_factory=list)
    url: Optional[str] = None

class PublicationEntry(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    venue: Optional[str] = None
    year: Optional[int] = None
    citations: Optional[int] = None
    url: Optional[str] = None
    abstract_summary: Optional[str] = None

class AwardEntry(BaseModel):
    name: str
    issuer: str
    year: str
    description: Optional[str] = None

class ExperienceEntry(BaseModel):
    role: str
    organization: str
    start_date: str
    end_date: Optional[str] = None
    description: str
    achievements: List[str] = Field(default_factory=list)

class ResearchProfile(BaseModel):
    basic_information: BasicInformation
    career_stage: str
    education: List[EducationEntry] = Field(default_factory=list)
    current_position: Optional[CurrentPosition] = None
    research_domains: List[str] = Field(default_factory=list)
    research_interests: List[str] = Field(default_factory=list)
    technical_skills: TechnicalSkills
    projects: List[ProjectEntry] = Field(default_factory=list)
    publications: List[PublicationEntry] = Field(default_factory=list)
    awards: List[AwardEntry] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    research_keywords: List[str] = Field(default_factory=list)
    industry_keywords: List[str] = Field(default_factory=list)
    preferred_roles: List[str] = Field(default_factory=list)
    preferred_companies: List[str] = Field(default_factory=list)
    preferred_research_labs: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    email_style: str
    writing_style: str
    research_strengths: List[str] = Field(default_factory=list)
    possible_weaknesses: List[str] = Field(default_factory=list)
    competitive_advantages: List[str] = Field(default_factory=list)
    summary: str
