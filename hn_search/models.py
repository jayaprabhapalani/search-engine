from hn_search.database import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, func,
    ForeignKey, UniqueConstraint, Index, PrimaryKeyConstraint,
)


class Stories(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    text = Column(Text)
    preprocessed_text = Column(Text)
    url = Column(Text, nullable=True)
    domain = Column(String(253), nullable=True)
    score = Column(Integer, nullable=True)
    descendants = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=True)


class StoryContent(Base):
    __tablename__ = "story_content"
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True)
    text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=True)
    word_count = Column(Integer, nullable=True)
    # status: pending | ok | failed | skipped | empty
    status = Column(String(16), nullable=False, server_default="pending")
    attempts = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=True)


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=True)
    __table_args__ = (
        UniqueConstraint("story_id", "chunk_index", name="uq_chunk_story_idx"),
        Index("ix_chunks_story_id", "story_id"),
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    model = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("chunk_id", "model", name="pk_chunk_embeddings"),
        Index("ix_chunk_embeddings_chunk_id", "chunk_id"),
    )


class SearchAnalytics(Base):
    __tablename__ = "search_analytics"
    id = Column(Integer, primary_key=True)
    query = Column(Text)
    results_count = Column(Integer)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
