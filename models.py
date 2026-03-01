from database import Base
from sqlalchemy import Column,Integer,String,Text

class Stories(Base):
    __tablename__="stories"
    id=Column(Integer,primary_key=True)
    title=Column(String)
    text=Column(Text)
    preprocessed_text=Column(Text)
    url=Column(Text,nullable=True)
    score=Column(Integer,nullable=True)