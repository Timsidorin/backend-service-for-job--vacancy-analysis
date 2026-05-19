from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class RawVacancy(Base):
    __tablename__ = 'raw_vacancies'

    uuid = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source = Column(String(50), nullable=False, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    full_text = Column(String, nullable=True)

    city = Column(String, nullable=True)
    region = Column(String, nullable=True)
    region_code = Column(String(20), nullable=True)

    employer = Column(String, nullable=True)
    salary_from = Column(Integer, nullable=True)
    salary_to = Column(Integer, nullable=True)
    currency = Column(String(10), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    parsed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_data = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    processed = relationship("ProcessedVacancy", back_populates="raw", uselist=False)


class ProcessedVacancy(Base):
    __tablename__ = 'processed_vacancies'

    uuid = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    raw_vacancy_uuid = Column(UUID(as_uuid=True), ForeignKey('raw_vacancies.uuid'), nullable=False, unique=True)

    skills = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    grade_prediction = Column(String(20), nullable=True)
    domain = Column(String(100), nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw = relationship("RawVacancy", back_populates="processed")
