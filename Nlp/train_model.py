import numpy as np
import pandas as pd
import matplotlib as plt
import seaborn as sns
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score
from sklearn.model_selection import train_test_split,cross_val_score,GridSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer,CountVectorizer
import joblib
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
import string

def clean_text():
    df=pd.read_csv("Training_Data/intent_training.csv")
    df["query"]=df["query"].apply(lambda x:x.lower())

    def removePunc(query):
        return query.translate(str.maketrans("","",string.punctuation))
    df["query"]=df["query"].apply(removePunc)

    def removeNumber(query):
        new=""
        for i in query:
            if not i.isdigit():
                new=new+i
        return new
    df["query"]=df["query"].apply(removeNumber)

    def removeEmoji(query):
        new=""
        for i in query:
            if i.isascii():
                new=new+i
        return new
    df["query"]=df["query"].apply(removeEmoji)

    stop_words=set(stopwords.words("english"))
    def removeStopWords(query):
        words=query.split()
        cleans_text=[]
        for i in words:
            if i not in stop_words:
                cleans_text.append(i)
        return " ".join(cleans_text)
    df["query"]=df["query"].apply(removeStopWords)
    return df

def trainModel():
    df=clean_text()
    X=df["query"]
    y=df["intent"]
    X_train,X_test,y_train,y_test=train_test_split(X,y,stratify=y,random_state=42,test_size=0.2)
    vectorizer=TfidfVectorizer()
    X_train_vect=vectorizer.fit_transform(X_train)
    X_test_vect=vectorizer.transform(X_test)
    model=LogisticRegression(max_iter=1000,class_weight="balanced")
    model.fit(X_train_vect,y_train)
    y_pred=model.predict(X_test_vect)
    accuracy=accuracy_score(y_test,y_pred)
    print(f"Accuracy Score : {round(accuracy*100,2)}")
    return model,vectorizer
def saveModel():
    model,vectorizer=trainModel()
    joblib.dump(model, "Model/intent_model.pkl")
    joblib.dump(vectorizer, "Model/tfidf_vectorizer.pkl")

saveModel()