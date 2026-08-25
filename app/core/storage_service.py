import os
import io
import mimetypes
import logging
import boto3
import botocore
from decouple import config
from flask import current_app

logger = logging.getLogger(__name__)

_s3_client = None

def get_s3_client():
    global _s3_client
    if _s3_client is None:
        endpoint = config('SUPABASE_BUCKET', default='')
        access_key = config('SUPABASE_BUCKET_API_KEY', default='')
        secret_key = config('SUPABASE_SECRET_ACCESS_KEY', default='')
        
        if endpoint and access_key and secret_key:
            _s3_client = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name='ap-northeast-1',
                config=botocore.config.Config(
                    s3={'addressing_style': 'path'},
                    signature_version='s3v4'
                )
            )
    return _s3_client


def get_bucket_name() -> str:
    return config('SUPABASE_BUCKET_NAME', default='DocMed-Bucket')


def upload_file_to_storage(file_obj, filename: str, content_type: str = None) -> str:
    """
    Uploads a file object or file-like stream to Supabase Storage Bucket (with local fallback).
    Returns the stored filename or relative path.
    """
    s3 = get_s3_client()
    bucket = get_bucket_name()

    # Determine mime-type
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = 'image/png'

    # Always ensure local copy exists as cache / fallback
    upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads'))
    os.makedirs(upload_folder, exist_ok=True)
    local_path = os.path.join(upload_folder, filename)

    # Read data from file_obj
    if hasattr(file_obj, 'read'):
        data = file_obj.read()
        # Save local copy
        with open(local_path, 'wb') as f:
            f.write(data)
        
        # Reset stream position if needed
        if hasattr(file_obj, 'seek'):
            try:
                file_obj.seek(0)
            except Exception:
                pass
    else:
        with open(local_path, 'rb') as f:
            data = f.read()

    # Upload to Supabase Storage S3
    if s3 and bucket:
        try:
            s3.put_object(
                Bucket=bucket,
                Key=f"uploads/{filename}",
                Body=data,
                ContentType=content_type
            )
            logger.info(f"Successfully uploaded {filename} to Supabase bucket '{bucket}/uploads/{filename}'")
        except Exception as e:
            logger.error(f"Failed to upload {filename} to Supabase S3: {e}")

    return filename


def get_file_url(filename: str) -> str:
    """
    Returns public URL for file in Supabase storage, or falls back to local static URL.
    """
    if not filename:
        return ""
    
    # If filename is already a full URL
    if filename.startswith('http://') or filename.startswith('https://'):
        return filename

    endpoint = config('SUPABASE_BUCKET', default='')
    bucket = get_bucket_name()
    
    # Supabase standard public URL format: https://<project>.supabase.co/storage/v1/object/public/<bucket>/uploads/<filename>
    # From S3 endpoint: https://<project>.storage.supabase.co/storage/v1/s3
    if endpoint and bucket:
        project_ref = endpoint.replace("https://", "").split(".")[0]
        return f"https://{project_ref}.supabase.co/storage/v1/object/public/{bucket}/uploads/{filename}"

    return f"/static/uploads/{filename}"
