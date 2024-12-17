from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from starlette.status import HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text as sql_text

import pandas as pd
import numpy as np
import asyncio
import simplejson as json
import time

import datetime as dt
import aiosmtplib
from email.mime.text import MIMEText
import os

from config import Config
from params import ParamChecker
from db_tables import Tables
import models
from auth_utils import AuthUtils

# Uvicorn initalize
app = FastAPI()

origins = ["*"] # * accepts requests from all ips
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

configs = Config()
params = ParamChecker()
tables = Tables()

async def async_get_item(session, sql_str):
    result = await session.execute(sql_text(sql_str))
    return result.fetchall(), 1

global coin_list_spot
coin_list_spot = []
async def update_global_data():
    global coin_list_spot
    async with SessionLocal() as session:
        try:
            # We only provide service for some of the coins that exists in binance.
            # We have a custom list for this list in our database that we constantly update.
            # So this list will be updated within the api code, every minute
            coin_list_spot_db, status = await async_get_item(session, "SELECT pair FROM COIN_LIST")
            if status == 1:
                coin_list_spot = pd.DataFrame(coin_list_spot_db).iloc[:, 0].tolist()
                
        except Exception as e:
            print("Error updating global data")

@app.on_event("startup")
async def startup_event():
    # Scheduled tasks
    asyncio.create_task(scheduled_tasks())

async def scheduled_tasks():
    while True:
        try:    
            await update_global_data()
            await asyncio.sleep(60)
        except Exception as e:
            print("Error: scheduled_tasks | ",e)

# DB engine
engine = create_async_engine(configs.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

#%% Website authentication endpoints

# Login endpoint. will check if e mail and password combination exists in our database
@app.post("/login", dependencies=[Depends(RateLimiter(times=configs.rate_limit, seconds=60))])
async def login_user(data: models.LoginUser, request: Request):
    async with SessionLocal() as session:
        async with session.begin():
            query = select(tables.WEBSITE).where(tables.WEBSITE.c.email == data.email)
            result = await session.execute(query)
            user_entry = result.fetchone()
            if not user_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid email or password")

            if not AuthUtils.check_password(data.password, user_entry.password.encode('utf-8')):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid email or password")

            activated = user_entry.email_verified  # Check if the email is activated
            return {
                "success": True, 
                "message": "Successfully logged in", 
                "api_key": user_entry.api_key,
                "activated": activated
            }

# Register endpoint
# Users need to enter the "apikey" they get from our telegram bot to register. We will check our database for the apikey's validty
# they also need to set a password 
@app.post("/register", dependencies=[Depends(RateLimiter(times=configs.rate_limit, seconds=60))])
async def register_user(data: models.RegisterUser, request: Request):
    async with SessionLocal() as session:
        async with session.begin():
            
            # Verify if the provided API key exists and is active.
            # if not, we will return an error
            # There's a mysql event that inactivates very old apikeys
            query = select(tables.APIKEYS).where(
                tables.APIKEYS.c.api_key == data.api_key,
                tables.APIKEYS.c.active == 1
            )
            result = await session.execute(query)
            api_key_entry = result.fetchone()
            if not api_key_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid or inactive API key")

            # Check if the email already exists in our database
            query = select(tables.WEBSITE).where(tables.WEBSITE.c.email == data.email)
            result = await session.execute(query)
            user_entry = result.fetchone()
            if user_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Email already exists")

            # Generate the verification code and set its expiry
            verification_code = AuthUtils.generate_verification_code()
            code_expiry = dt.datetime.utcnow() + dt.timedelta(hours=1)  # Verification code will expire in 1 hour
            code_created = dt.datetime.utcnow()

            # Hash the password and insert the new user to db
            hashed_password = AuthUtils.hash_password(data.password)
            insert_stmt = tables.WEBSITE.insert().values(
                email=data.email,
                password=hashed_password.decode('utf-8'),
                api_key=data.api_key,
                email_verified=False,
                verification_code=verification_code,
                code_expiry=code_expiry,
                code_created=code_created
            )
            await session.execute(insert_stmt)
            await session.commit()

    # Send verification code to user's email async
    asyncio.create_task(send_verification_email(data.email, verification_code))

    # Immediately return response without waiting for email to be sent
    return {"success": True, "message": "User registered successfully. Please check your email for the verification code."}

    
# This function sends e-mail verification when registering
async def send_verification_email(to_address, verification_code):
    subject = "Verify your email address"
    body = f"Please use the following code to verify your email address: {verification_code}"

    msg = MIMEText(body)
    msg["Subject"] = subject # subject of the mail
    msg["From"] = configs.smtp_username # our e-mail address
    msg["To"] = to_address # target address

    try:
        async with aiosmtplib.SMTP(hostname=configs.smtp_server, port=configs.smtp_port, use_tls=True) as server:
            await server.login(configs.smtp_username, configs.smtp_password) # need to login to our e mail first
            await server.sendmail(configs.smtp_username, to_address, msg.as_string()) # send the e mail
    except aiosmtplib.SMTPException as e:
        print(f"Failed to send email to {to_address}: {e}")
   
# This endpoint verifies the e mail verification code of the code user provided
@app.post("/verify_email", dependencies=[Depends(RateLimiter(times=configs.rate_limit, seconds=60))])
async def verify_email(data: models.VerifyEmailCode):
    async with SessionLocal() as session:
        async with session.begin():
            # Retrieve the user data from the database website table
            query = select(tables.WEBSITE).where(tables.WEBSITE.c.email == data.email)
            result = await session.execute(query)
            user_entry = result.fetchone()
            if not user_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid email")

            # Check the verification code and expiry
            if user_entry.verification_code != data.verification_code:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid verification code")
            
            if user_entry.code_expiry is not None:
                if datetime.utcnow() > user_entry.code_expiry:
                    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Verification code expired")

            # If everything is allright, we will mark the email as verified
            update_stmt = tables.WEBSITE.update().where(
                tables.WEBSITE.c.email == data.email
            ).values(email_verified=True, verification_code=None, code_expiry=None, code_created=None) # we will delete other values
            await session.execute(update_stmt)
            await session.commit()

            return {"success": True, "message": "Email verified successfully"}

     

@app.post("/resend_verification_code", dependencies=[Depends(RateLimiter(times=configs.rate_limit, seconds=60))])
async def resend_verification_code(data: models.LoginUser, request: Request):
    async with SessionLocal() as session:
        async with session.begin():
            
            # Fetch the user data using email address we got
            query = select(tables.WEBSITE).where(tables.WEBSITE.c.email == data.email)
            result = await session.execute(query)
            user_entry = result.fetchone()
            if not user_entry:
                raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Email not found")
            
            # If e mail exists, Verify the password
            if not AuthUtils.check_password(data.password, user_entry.password.encode('utf-8')):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid email or password")

            # Handle case where code_created might be NULL
            code_created_time = user_entry.code_created
            if code_created_time is not None:
                current_time = dt.datetime.utcnow()
                time_difference = current_time - code_created_time

                if time_difference < dt.timedelta(minutes=5):
                    return {"success": False, "message": "Not enough time has passed since the last verification code was sent. Please wait before requesting a new one."}
                
            # If code_created is NULL, allow the generation of a new code immediately
            # Generate a new verification code and update the record
            new_code = AuthUtils.generate_verification_code()
            code_expiry = dt.datetime.utcnow() + dt.timedelta(hours=1)  # Code expires in 1 hour
            
            update_stmt = tables.WEBSITE.update().where(
                tables.WEBSITE.c.email == data.email
            ).values(
                verification_code=new_code,
                code_expiry=code_expiry,
                code_created=dt.datetime.utcnow()  # Update the code_created column
            )
            await session.execute(update_stmt)
            await session.commit()
            
            # Send the verification email with the new code
            await send_verification_email(data.email, new_code)
            return {"success": True, "message": "Verification code resent"}
        

# Change API Key Endpoint.
# Users can change their apikeys. First, they need to get a new api key from telegram
@app.post("/change_apikey", dependencies=[Depends(RateLimiter(times=configs.rate_limit, seconds=60))])
async def change_api_key(data: models.ChangeAPIKey , request: Request):
    async with SessionLocal() as session:
        async with session.begin():
            # Fetch user data
            query = select(tables.WEBSITE).where(
                tables.WEBSITE.c.email == data.email,
                # tables.WEBSITE.c.api_key == data.old_api_key
            )
            result = await session.execute(query)
            user_entry = result.fetchone()
            if not user_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="User not found")

            # Api key already being used
            query = select(tables.WEBSITE).where(tables.WEBSITE.c.api_key == data.new_api_key)
            result = await session.execute(query)
            api_key_in_use = result.fetchone()
            if api_key_in_use:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="New API key already in use")

            # Update the new api key
            update_user_stmt = tables.WEBSITE.update().where(
                tables.WEBSITE.c.email == data.email
            ).values(api_key=data.new_api_key)
            await session.execute(update_user_stmt)
            await session.commit()
            return {"success": True, "message": "API key changed successfully"}

# Change Password Endpoint
@app.post("/change_password", dependencies=[Depends(RateLimiter(times=configs.rate_limit, seconds=60))])
async def change_password(data: models.ChangePassword , request: Request):
    async with SessionLocal() as session:
        async with session.begin():
            query = select(tables.WEBSITE).where(tables.WEBSITE.c.email == data.email)
            result = await session.execute(query)
            user_entry = result.fetchone()
            if not user_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid email or password")

            if not AuthUtils.check_password(data.old_password, user_entry.password.encode('utf-8')):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid old password")

            hashed_password = AuthUtils.hash_password(data.new_password)

            update_stmt = tables.WEBSITE.update().where(
                tables.WEBSITE.c.email == data.email
            ).values(password=hashed_password.decode('utf-8'))
            await session.execute(update_stmt)
            await session.commit()
            return {"success": True, "message": "Password changed successfully"}



# Every api key thats sent to an endpoint needs to be verified.
# Users create their apikeys from our telegram app. 
# Its necessary to register to website and use any endpoint that returns the datas we provide
async def verify_api_key(api_key: str, request: Request):
    async with SessionLocal() as session:
        async with session.begin():
            # We'll check if the api key exists in database, and if its still active
            query = select(tables.APIKEYS).where(
                tables.APIKEYS.c.api_key == api_key,
                tables.APIKEYS.c.active == 1
            )
            result = await session.execute(query)
            api_key_entry = result.fetchone()
            if not api_key_entry:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid or inactive API key")
            

            # Verify if the email is activated in the "WEBSITE" table. Unverified mail users wont get authorization
            query = select(tables.WEBSITE).where(
                tables.WEBSITE.c.api_key == api_key
            )
            result = await session.execute(query)
            user_entry = result.fetchone()
            if not user_entry or not user_entry.email_verified:
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Email is not verified")
            
            return api_key

#%% Data endpoint
def get_api_key_from_query(request: Request):
    return request.query_params.get("api_key")

@app.get("/get_data", dependencies=[Depends(RateLimiter(times=configs.graph_data_rate_limit, seconds=60, key_func=get_api_key_from_query))])
async def get_data(
    request: Request,
    api_key: str = Query(...),
    graph: str = "volplot",
    parite: str = "BTC",
    borsa: str = "binance",
    interval: str = "5m",
    candle_adet: int = 100,
    historical: int = 0,   
):
    global coin_list_spot
    

    await verify_api_key(api_key, request)
    hata = False
    
    print("Api key control")
    
    # Graph - table control
    if graph.lower() not in params.grafik_listesi: raise HTTPException(status_code=400, detail="Invalid data type")
    graph = graph.lower()
    
    # Pair control
    parite = parite.upper()
    hata,parite = params.check_pair(parite,coin_list_spot,graph,borsa=borsa)
    if hata: raise HTTPException(status_code=400, detail="Invalid pair")
    
    # Exchange control
    hata = params.check_borsa(graph,borsa)
    if hata: raise HTTPException(status_code=400, detail="Invalid exchange")
    else: borsa = borsa.lower()
    
    # Interval, adet historical kontrol
    if interval not in params.valid_intervals: 
        raise HTTPException(status_code=400, detail=f"Invalid interval. Try: {', '.join(params.valid_intervals)}")
    else: interval = interval.lower()
    
    if int(candle_adet) > params.max_candle_adet: raise HTTPException(status_code=400, detail=f"Candle amount too large. (Max: {params.max_candle_adet})")
    if int(historical) > params.max_historical: raise HTTPException(status_code=400, detail=f"Historical data too old. (Max: {params.max_historical} candles.)")
    
    # Futmap type
    if "futmap" in graph.lower():
        graph_temp = graph.lower().replace("futmap","")
        if graph_temp == "": graph_temp = "1" # futmap -> futmap1
        if graph_temp not in params.valid_futmaps:
            raise HTTPException(status_code=400, detail="Invalid Futmap")            
    
    async with SessionLocal() as session:
        #placeholder
        sql_str = f"SELECT * FROM DATA where pair = '{parite}'"
        data = await async_get_item(session, sql_str)


    # "data" returns dataframes and arrays. we will return this response to the user
    response_data = {
            "dataframes": [df.to_dict(orient="records") for df in data if isinstance(df, pd.DataFrame)],
            "arrays": [arr.tolist() for arr in data if isinstance(arr, np.ndarray)]
        }
    
    return JSONResponse(content=json.dumps(response_data, ignore_nan=True)) # nan value sıkıntı cikarmasin diye simplejson ile dumpliyoruz

if __name__ == "__main__":
    import uvicorn
    cpus = os.cpu_count()
    print(f"Starting Uvicorn on {cpus} cores")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, workers = cpus) # nginx proxy