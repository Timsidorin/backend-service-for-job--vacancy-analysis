from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class RawVacancyBase(BaseModel):
    source: str
    url: str
    title: str
    description: Optional[str] = None
    full_text: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    region_code: Optional[str] = None
    employer: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency: Optional[str] = None
    published_at: Optional[datetime] = None
    raw_data: Dict[str, Any] = {}


class RawVacancyCreate(RawVacancyBase):
    pass


class RawVacancyRead(RawVacancyBase):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    parsed_at: datetime


class ProcessedVacancyCreate(BaseModel):
    raw_vacancy_uuid: UUID
    skills: Dict[str, List[str]]
    grade_prediction: Optional[str] = None
    domain: Optional[str] = None


class ProcessedVacancyRead(ProcessedVacancyCreate):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    processed_at: datetime
    raw_info: Optional[RawVacancyRead] = None
