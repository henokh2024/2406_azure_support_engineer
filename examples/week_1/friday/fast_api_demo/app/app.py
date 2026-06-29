import time
import logging
from typing import List
from fastapi import FastAPI, HTTPException, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from app.dao import SystemLogDAO, UserDAO, UserRegistrationError, InvalidCredentialsError
from app.exceptions import DatabaseConnectionError, LogCreationError

from app.auth_util import create_access_token, decode_verify_token
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

log_dao = SystemLogDAO()
user_dao = UserDAO(system_log_dao=log_dao)

app = FastAPI(title = "FastAPI Demo Application")
security = HTTPBearer()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log incoming requests and their responses."""
    start_time = time.time()
    response = await call_next(request)
    logging.info(f"Request: {request.method} {request.url} - Status: {response.status_code} - Duration: {time.time() - start_time:.4f}s")
    return response

class Authpayload(BaseModel):
    username: str = Field(..., example="engineer-alpha")
    password: str = Field(..., min_length = 6, example="supersecret123")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class LogPayload(BaseModel):
    host: str 
    severity: str 
    message: str 

def verify_sre_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Interceptor that parses out the bearer toekn and verifies signiture fiels."""
    token = credentials.credentials
    
    token_payload = decode_verify_token(token)

    return {"identity": token_payload.get("sub")}

@app.post("/auth/register", response_model=TokenResponse)
async def register_user(auth_data: Authpayload):
    try:
        user = user_dao.create_user(username=auth_data.username, password=auth_data.password)
        access_token = create_access_token(data={"sub": user.username})
        return TokenResponse(access_token=access_token, token_type="bearer")
    except UserRegistrationError as e:
        logging.error(f"Error occurred while registering user: {e}")
        raise HTTPException(status_code=400, detail="User registration failed")
    
    @app.post("/auth/login", response_model=TokenResponse, status_code=200)
    async def login_user(auth_data: Authpayload):
        try:
            user = user_dao.authenticate_user(username=auth_data.username, password=auth_data.password)
            access_token = create_access_token(data={"sub": user.username})
            return TokenResponse(access_token=access_token, token_type="bearer")
        except InvalidCredentialsError as e:
            logging.error(f"Invalid credentials provided: {e}")
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
    @app.post("/logs", status_code=201, dependencies=[Depends(verify_sre_jwt_token)])
    async def create_log(log_data: LogPayload):
        try:
            log_dao.create_log(host=log_data.host, severity=log_data.severity, message=log_data.message)
            return {"message": "Log entry created successfully"}
        except LogCreationError as e:
            logging.error(f"Error occurred while creating log entry: {e}")
            raise HTTPException(status_code=400, detail="Failed to create log entry")
        