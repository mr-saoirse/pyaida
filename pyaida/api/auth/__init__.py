import os
import firebase_admin
from firebase_admin import credentials
import json
from firebase_admin import auth
from fastapi import Depends, HTTPException 
from fastapi.security import OAuth2PasswordBearer

"""add this sp we can get the user details"""
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    
def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token  # returns user info from Firebase
   
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token verification error: {str(e)}")

"""we init with firebase auth in this case"""
try:
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    
    print(f'parsing |{repr(service_account_json)}|')
    service_account_json =  json.loads(service_account_json)
 
    """NB - replace these or you get an encoding error"""
    service_account_json['private_key'] = service_account_json['private_key'].replace("\\n", "\n")

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_json)
        firebase_admin.initialize_app(cred)
except Exception as e:
    print('Failing', e)
    raise
finally:
    pass