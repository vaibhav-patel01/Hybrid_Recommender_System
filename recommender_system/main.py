
import pandas as pd
import ast
import os
import pymssql
from fastapi import FastAPI,Query , Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from recommender_system.recommender import hybrid_recommend1, hybrid_recommende2
from recommender_system.search_aid import search_anime_id, search_all_anime_id

app = FastAPI()
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_path = os.path.join(base_dir, "data", "fully_final_metadata.csv")
df = pd.read_csv(csv_path, converters={
    'title': ast.literal_eval,
    'genre': ast.literal_eval,
    'tags': ast.literal_eval,
    'studios': ast.literal_eval
} )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Safely convert SQL string arrays back to Python lists
# def safe_eval(val):
#     try:
#         return ast.literal_eval(val) if isinstance(val, str) else val
#     except (ValueError, SyntaxError):
#         return val
#
# for col in ['title', 'genre', 'tags', 'studios']:
#     if col in df.columns:
#         df[col] = df[col].apply(safe_eval)


def info(df, aid):
    # Filter and create a copy to avoid SettingWithCopyWarning
    temp = df[df["id"] == aid].copy()
    
    # Check if the ID actually exists to prevent an IndexError
    if temp.empty:
        return [] 
        
    # Get the type of the first matched row
    item_type = temp["type"].iloc[0]
    
    # Drop columns based on type
    if item_type in ["MANHWA", "MANGA"]:
        temp = temp.drop(columns=["episodes", "popularity", "source"], errors="ignore")
    else:
        temp = temp.drop(columns=["chapters", "volumes", "popularity"], errors="ignore")
        
    # Apply title transformation (done once for both conditions)
    temp["title"] = temp["title"].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else x[0])
    
    # Return as list of dictionaries
    return temp.to_dict(orient="records")

@app.get("/")
def home_page():
    animes = df[df["type"] == "ANIME"].sort_values(by="popularity", ascending=False)[
        ["id", "title", "coverImage"]]
    animes["title"] = animes["title"].apply(lambda x: x[1] if len(x) > 1 else x[0])
    animes = animes.iloc[:12].to_dict(orient="records")

    manhwa = df[df["type"] == "MANHWA"].sort_values(by="popularity", ascending=False)[
        ["id", "title", "coverImage"]]
    manhwa["title"] = manhwa["title"].apply(lambda x: x[1] if len(x) > 1 else x[0])
    manhwa = manhwa.iloc[:12].to_dict(orient="records")

    return JSONResponse(status_code= 200, content={
        "animes": animes,
        "manhwa": manhwa
    })

@app.get("/search")
def search(q : str  = Query(...,description= "user gives a search query")):

    try:
        result = search_all_anime_id(q,df)
        return JSONResponse(status_code= 200, content={
            "search_result" : result
        })
    except Exception as e:
        return JSONResponse(status_code= 500, content= str(e) )

@app.get("/recommend/{id}")
def recommend(id : int = Path(..., description=  "recommend the content based on the given anime id"),
                             limit : int = Query(default= 20,description=  "how many recommendations, not neccessary")):
    try:
        result = hybrid_recommende2(id, df, limit )
        result = result.to_dict(orient="records")
        return JSONResponse(status_code= 200, content={
            "recommendations" : result
        })
    except Exception as e:
        return JSONResponse(status_code= 500, content= str(e) )

@app.get("/info/{id}")
def get_info(id : int = Path(..., description=  "recommend the content based on the given anime id")) :
    details= info(df,id)
    try:
        other_recommendations = hybrid_recommende2(id, df)
        other_recommendations = other_recommendations.to_dict(orient="records")
        return JSONResponse(status_code= 200, content={
            "detail": details,
            "similar": other_recommendations
        })
    except Exception as e:
        return JSONResponse(status_code= 500, content= str(e) )

@app.get("/health")
def health_check():
    return {
        "status" : "OK"
    }


