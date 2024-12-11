from fastapi import FastAPI
from pyaida.api.routers import references
from pathlib import Path
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pyaida.api.auth import verify_token
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles
from fastapi import Request

security = HTTPBearer()

async def get_current_user(token: HTTPAuthorizationCredentials = Security(security)):
    """
    Extracts and verifies the Firebase ID token from the Authorization header.
    """
    print(token)
    decoded_token = verify_token(token.credentials)
    if not decoded_token:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return decoded_token



app = FastAPI()

#app.mount("/static", StaticFiles(directory="./static",html = True), name="static")
   
origins = [
    "http://localhost:8002",
    "chrome-extension://kaianlmbmcmbnaoeghilikjnnkejbchb"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(references.router, prefix="/resources", tags=["resources"])
 
def start():
    import uvicorn

    uvicorn.run(
        f"{Path(__file__).stem}:app",
        host="0.0.0.0",
        port=8002,
        log_level="debug",
        reload=True,
    )


if __name__ == "__main__":
    """   
    You can start the dev with this in the root above the lib pyaida
    uvicorn pyaida.api.main:app --port 8002 --reload
    http://127.0.0.1:8002/docs
    
    """
    
    start()
    
