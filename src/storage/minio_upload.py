import os
import json
import time
import shutil
import hashlib
import logging
import asyncio
import threading
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from src.notifier import send_message, send_error_notification

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MinioUploader:
    def __init__(self, minio_client, bucket_name):
        self.client = minio_client
        self.bucket_name = bucket_name

    def check_bucket_exists(self):
        try:
            return self.client.bucket_exists(self.bucket_name)
        except S3Error as e:
            logger.error(f"Error checking bucket existence: {e}")
            return False

    def create_bucket(self):
        try:
            if not self.check_bucket_exists():
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' created successfully.")
            else:
                logger.info(f"Bucket '{self.bucket_name}' already exists.")
        except S3Error as e:
            logger.error(f"Error creating bucket '{self.bucket_name}': {e}")

    def upload_file(self, file_path, object_name):
        try:
            if not os.path.exists(file_path):
                logger.error(f"File '{file_path}' does not exist.")
                return False
            self.client.fput_object(self.bucket_name, object_name, file_path)
            logger.info(f"Uploaded file '{file_path}' as '{object_name}'.")
            return True
        except S3Error as e:
            logger.error(f"S3Error uploading '{file_path}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error uploading '{file_path}': {e}")
        return False

    def stat_object(self, object_name):
        try:
            return self.client.stat_object(self.bucket_name, object_name)
        except S3Error as e:
            logger.error(f"Error stat'ing object '{object_name}': {e}")
            return None

def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error computing MD5 for {file_path}: {e}")
        return None

def upload_file_with_integrity_check(uploader, file_path, final_object_name, retries=3, delay=5):
    local_md5 = compute_md5(file_path)
    if not local_md5:
        return False

    for attempt in range(retries):
        if not uploader.upload_file(file_path, final_object_name):
            logger.warning(f"Attempt {attempt+1}: Failed to upload {file_path} as {final_object_name}. Retrying in {delay} sec...")
            time.sleep(delay)
            continue

        stat = uploader.stat_object(final_object_name)
        if not stat:
            logger.warning(f"Attempt {attempt+1}: Could not stat {final_object_name}. Retrying in {delay} sec...")
            time.sleep(delay)
            continue

        etag = stat.etag.strip('\"')
        if etag == local_md5:
            logger.info(f"Integrity check passed for {file_path} (ETag: {etag}).")
            return True
        else:
            logger.warning(f"Integrity check failed for {file_path}: local MD5 {local_md5} vs ETag {etag}. Retrying in {delay} sec...")
        time.sleep(delay)
    return False

def upload_folder(uploader, folder_path, base_object_prefix="results", retries=3, delay=5):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            local_file = os.path.join(root, file)
            rel_path = os.path.relpath(local_file, folder_path)
            object_name = os.path.join(base_object_prefix, rel_path).replace(os.sep, "/")
            logger.info(f"Uploading {local_file} as {object_name}...")
            success = upload_file_with_integrity_check(uploader, local_file, object_name, retries, delay)
            if not success:
                logger.error(f"Failed to upload {local_file} after {retries} attempts.")

def update_upload_history(progress_file, record):
    try:
        if os.path.exists(progress_file):
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
        else:
            progress = {}
        if "upload_history" not in progress:
            progress["upload_history"] = []
        progress["upload_history"].append(record)
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=4)
        logger.info(f"Updated upload history with record: {record}")
    except Exception as e:
        logger.error(f"Error updating upload history in {progress_file}: {e}")

def notify_upload_status(message, is_error=False):
    try:
        if is_error:
            asyncio.run(send_error_notification(message))
        else:
            asyncio.run(send_message(message))
    except Exception as e:
        logger.error(f"Error sending notification: {e}")

def create_temp_copy(src_folder):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    temp_folder = f"/tmp/data-{timestamp}"
    try:
        shutil.copytree(src_folder, temp_folder)
        logger.info(f"Copied '{src_folder}' to temporary folder '{temp_folder}'.")
        return temp_folder
    except Exception as e:
        logger.error(f"Error copying folder {src_folder} to temporary folder: {e}")
        return None
def start_hourly_sync(minio_client, bucket_name, result_folder, job_result_file, progress_file, interval=3600):
    def sync_loop():
        while True:
            try:
                upload_to_minio_full(minio_client, bucket_name, result_folder, job_result_file, progress_file)
                logger.info("Hourly sync completed.")
            except Exception as e:
                logger.error(f"Hourly sync error: {e}")
            time.sleep(interval)
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    logger.info("Hourly sync thread started.")

def upload_to_minio_full(minio_client, bucket_name, result_folder, job_result_file, progress_file):
    uploader = MinioUploader(minio_client, bucket_name)
    uploader.create_bucket()
    current_time = datetime.now().isoformat()
    
    temp_folder = create_temp_copy(result_folder)
    if temp_folder:
        logger.info(f"Uploading temporary folder '{temp_folder}' under prefix 'results'...")
        upload_folder(uploader, temp_folder, base_object_prefix="results")
        update_upload_history(progress_file, {
            "timestamp": current_time,
            "action": "upload_folder",
            "folder": temp_folder,
            "status": "completed"
        })
        try:
            shutil.rmtree(temp_folder)
            logger.info(f"Temporary folder '{temp_folder}' removed after upload.")
        except Exception as e:
            logger.error(f"Error removing temporary folder '{temp_folder}': {e}")
    else:
        update_upload_history(progress_file, {
            "timestamp": current_time,
            "action": "upload_folder",
            "folder": result_folder,
            "status": "failed"
        })
        notify_upload_status("Failed to create temporary folder for results upload.", is_error=True)
    
    if os.path.exists(job_result_file):
        base_result = os.path.basename(job_result_file)
        object_name_result = os.path.join("job_results", base_result).replace(os.sep, "/")
        logger.info(f"Uploading job result file '{job_result_file}' as '{object_name_result}'...")
        if upload_file_with_integrity_check(uploader, job_result_file, object_name_result):
            update_upload_history(progress_file, {
                "timestamp": current_time,
                "action": "upload_job_result",
                "file": job_result_file,
                "object": object_name_result,
                "status": "completed"
            })
            notify_upload_status(f"Job result file '{job_result_file}' uploaded successfully.")
        else:
            update_upload_history(progress_file, {
                "timestamp": current_time,
                "action": "upload_job_result",
                "file": job_result_file,
                "object": object_name_result,
                "status": "failed"
            })
            notify_upload_status(f"Failed to upload job result file '{job_result_file}'.", is_error=True)
    else:
        logger.error(f"Job result file '{job_result_file}' not found.")
        update_upload_history(progress_file, {
            "timestamp": current_time,
            "action": "upload_job_result",
            "file": job_result_file,
            "status": "not_found"
        })
        notify_upload_status(f"Job result file '{job_result_file}' not found.", is_error=True)
    
    if os.path.exists(progress_file):
        base_progress = os.path.basename(progress_file)
        object_name_progress = os.path.join("progress", base_progress).replace(os.sep, "/")
        logger.info(f"Uploading progress file '{progress_file}' as '{object_name_progress}'...")
        if upload_file_with_integrity_check(uploader, progress_file, object_name_progress):
            update_upload_history(progress_file, {
                "timestamp": current_time,
                "action": "upload_progress",
                "file": progress_file,
                "object": object_name_progress,
                "status": "completed"
            })
            notify_upload_status("Progress file uploaded successfully.")
        else:
            update_upload_history(progress_file, {
                "timestamp": current_time,
                "action": "upload_progress",
                "file": progress_file,
                "object": object_name_progress,
                "status": "failed"
            })
            notify_upload_status("Failed to upload progress file.", is_error=True)
    else:
        logger.error(f"Progress file '{progress_file}' not found.")
        update_upload_history(progress_file, {
            "timestamp": current_time,
            "action": "upload_progress",
            "file": progress_file,
            "status": "not_found"
        })
        notify_upload_status("Progress file not found.", is_error=True)
