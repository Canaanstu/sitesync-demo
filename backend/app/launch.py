"""Public launch requests. No public listing and no automatic email sends."""
import hashlib
import re
from typing import Literal
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import LaunchRequest
from .security import encrypt_token, rate_limit

router=APIRouter(prefix='/api/launch')

class Signup(BaseModel):
    email: str = Field(min_length=5,max_length=254)
    company: str = Field(default='',max_length=160)
    interest: Literal['demo','launch'] = 'demo'
    consent: Literal[True]
    website: str = Field(default='',max_length=200)

    @field_validator('email')
    @classmethod
    def valid_email(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+",value):
            raise ValueError('Enter a valid company email address.')
        return value

@router.post('/requests',status_code=202)
def signup(body:Signup,request:Request,db:Session=Depends(get_db)):
    rate_limit('launch:'+str(request.client.host if request.client else 'unknown'),limit=15,period=60)
    result={'message':'Your request is saved. The SiteSync team can contact you about beta availability. No launch date or demo appointment is confirmed yet.'}
    if body.website:
        return result
    digest=hashlib.sha256(body.email.encode()).hexdigest()
    row=db.scalar(select(LaunchRequest).where(LaunchRequest.email_hash==digest,LaunchRequest.interest==body.interest))
    if not row:
        db.add(LaunchRequest(email_hash=digest,email_encrypted=encrypt_token(body.email),company_encrypted=encrypt_token(body.company.strip()),interest=body.interest,consent_version='launch-contact-v1'))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # An identical concurrent request was already saved.
    return result
