import uuid

from sqlalchemy import Column, String, Boolean, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from service.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    full_name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    is_email_verified = Column(Boolean, default=False)
    need_to_connected_social = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    auth_providers = relationship("AuthProvider", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    social_credentials = relationship("SocialCredentials", back_populates="user", uselist=False)


class AuthProvider(Base):
    __tablename__ = "auth_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_user_id = Column(String(255), nullable=True)
    password_hash = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    user = relationship("User", back_populates="auth_providers")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(Text, nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)
    revoked_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")


class SocialCredentials(Base):
    __tablename__ = "social_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    twitter_access_token = Column(Text, nullable=True)
    twitter_refresh_token = Column(Text, nullable=True)
    twitter_token_expires_at = Column(TIMESTAMP, nullable=True)
    twitter_user_id = Column(String(255), nullable=True)
    reddit_access_token = Column(Text, nullable=True)
    reddit_refresh_token = Column(Text, nullable=True)
    reddit_token_expires_at = Column(TIMESTAMP, nullable=True)
    reddit_username = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="social_credentials")
    
    
    