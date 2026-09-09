import os
import uvicorn
from dotenv import load_dotenv
from pathlib import Path
from .main import create_app

if __name__=='__main__':
    load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
    host=os.getenv('APP_HOST','127.0.0.1')
    uvicorn.run(create_app(),host=host,port=int(os.getenv('PORT','8000')),proxy_headers=False)
