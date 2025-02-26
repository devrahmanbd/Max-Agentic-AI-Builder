import random

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)

PROXY_ENABLED = True

PROXY_STRINGS = [
    "http://user:pass@hostname:port/"
]

def get_random_proxy():
    return random.choice(PROXY_STRINGS)

def get_google_proxy():
    if PROXY_ENABLED:
        proxy_str = get_random_proxy()
        return {"http": proxy_str, "https": proxy_str}
    return None

REQUEST_TIMEOUT = 5  

MAX_RETRIES = 3
BACKOFF_INITIAL = 15  
BACKOFF_MULTIPLIER = 1.5  

MINIO_ENDPOINT = "Minio End Point"
MINIO_ACCESS_KEY = "Minio Access Key"
MINIO_SECRET_KEY = "Minio Secret ID"
MINIO_SECURE = False
BUCKET_NAME = "Minio Bucket Name"

RESULT_FOLDER = "./data/results"       
JOB_RESULT_FILE = "{jobname}-results.txt"  
PROGRESS_FILE = "progress.json"      

def get_job_result_file(jobname):
    return JOB_RESULT_FILE.format(jobname=jobname)
