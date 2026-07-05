import os
import uuid
from app import get_s3
from werkzeug.utils import secure_filename
from app.utils.sanitize import validate_file_magic

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOC_EXT = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXT | ALLOWED_DOC_EXT


def allowed_file(filename, allowed=None):
    allowed = allowed or ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def upload_file(file, folder='uploads'):
    """Upload a file to S3 after extension + magic-byte validation."""
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    # Magic-byte check — rejects files with spoofed extensions
    if not validate_file_magic(file):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    key = f"{folder}/{uuid.uuid4().hex}.{ext}"
    s3 = get_s3()
    bucket = os.getenv('S3_BUCKET_NAME')
    try:
        s3.upload_fileobj(
            file,
            bucket,
            key,
            ExtraArgs={
                'ContentType': file.content_type or 'application/octet-stream',
                'ACL': 'public-read',
            }
        )
        endpoint = os.getenv('S3_ENDPOINT_URL').rstrip('/')
        return f"{endpoint}/{bucket}/{key}"
    except Exception as e:
        print(f"S3 upload error: {e}")
        return None


def delete_file(file_url):
    if not file_url:
        return
    try:
        endpoint = os.getenv('S3_ENDPOINT_URL').rstrip('/')
        bucket = os.getenv('S3_BUCKET_NAME')
        key = file_url.replace(f"{endpoint}/{bucket}/", '')
        get_s3().delete_object(Bucket=bucket, Key=key)
    except Exception as e:
        print(f"S3 delete error: {e}")
