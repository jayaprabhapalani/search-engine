import re
import nltk
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
nltk.download("stopwords")
nltk.download("punkt")

stop_words=set(stopwords.words("english"))
stemmer=PorterStemmer()

def preprocess_text(text:str)->str:
    text=text.lower()
    processed_text=re.sub('[^a-z\s]',"",text)
    split_text=processed_text.split()
    stop_words_removed=[r for r in split_text if r not in stop_words]
    stemming=[stemmer.stem(word) for word in stop_words_removed]    
    return ' '.join(stemming)
    

def preprocess_stories(stories:list)->list:

    for story in stories:
        preprocessed_text=preprocess_text(story["text"])
        story["preprocessed_text"]=preprocessed_text
    
    return stories 

# if __name__=="__main__":
#     sample="Ask HN: Why is Python so popular for Machine Learning?"
#     print(preprocess_text(sample))
       
        
    
