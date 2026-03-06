from hn_search.database import Base
from sqlalchemy import Column,Integer,String,Text,DateTime,func

class Stories(Base):
    __tablename__="stories"
    id=Column(Integer,primary_key=True)
    title=Column(String)
    text=Column(Text)
    preprocessed_text=Column(Text)
    url=Column(Text,nullable=True)
    score=Column(Integer,nullable=True)
    
class SearchAnalytics(Base):
    __tablename__="search_analytics"
    id=Column(Integer,primary_key=True)
    query=Column(Text)
    results_count=Column(Integer)
    timestamp=Column(DateTime(timezone=True),server_default=func.now())