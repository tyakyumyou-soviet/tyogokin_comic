import io
import os
import json
import mimetypes
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.http import MediaFileUpload

import mimetypes
import logging

from django.core.cache import cache

from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)

def get_drive_service(google_account):
    # GoogleAccount.credentials_jsonに保存された認証情報を使って、Driveサービスオブジェクトを作成する
    credentials_data = json.loads(google_account.credentials_json)
    creds = Credentials.from_authorized_user_info(credentials_data)

    if creds.expired:
        if creds.refresh_token:
            try:
                creds.refresh(google_requests.Request())
            except Exception as e:
                # refresh_tokenでの更新が失敗した場合は、アカウントの再認証が必要とするエラーを投げる
                raise Exception("アクセストークンの更新に失敗しました。再認証してください。エラー: " + str(e))
        else:
            # refresh_tokenがない場合も再認証が必要
            raise Exception("アクセストークンが期限切れです。再認証してください。")
        
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service

def upload_file_to_drive(file_path, file_name, google_account):
    drive_service = get_drive_service(google_account)
    # ファイルをバイナリで読み込む
    with open(file_path, 'rb') as f:
        file_content = io.BytesIO(f.read())
    # ファイル名からMIMEタイプを推測
    mime_type, _ = mimetypes.guess_type(file_name)
    if not mime_type:
        mime_type = 'application/octet-stream'
    media = MediaIoBaseUpload(file_content, mimetype=mime_type)
    file_metadata = {'name': file_name}
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = uploaded_file.get('id')
    if not file_id:
        raise Exception("アップロード後のファイルIDが取得できませんでした。")
    
    # ここでファイルを公開設定に変更
    make_file_public(drive_service, file_id)
    
    return uploaded_file



def make_file_public(drive_service, file_id):
    permission = {
        'role': 'reader',
        'type': 'anyone'
    }
    drive_service.permissions().create(
        fileId=file_id,
        body=permission
    ).execute()

def get_free_storage(google_account):
    """
    指定したGoogleアカウントの空き容量（バイト単位）を返す。
    キャッシュがあればその値を利用し、なければAPIから取得する。
    このキャッシュは、アップロードまたは削除時に明示的に無効化されることを前提とする。
    """
    cache_key = f"free_storage_{google_account.id}"
    cached_free = cache.get(cache_key)
    if cached_free is not None:
        return cached_free

    # APIから取得
    drive_service = get_drive_service(google_account)
    about_info = drive_service.about().get(fields="storageQuota").execute()
    storage_quota = about_info.get("storageQuota", {})

    limit_str = storage_quota.get("limit")
    usage_str = storage_quota.get("usage")
    try:
        if not limit_str or limit_str == "0":
            limit = 15 * 1024 ** 3  # 15GB
        else:
            limit = int(limit_str)
        usage = int(usage_str) if usage_str else 0
    except ValueError:
        limit = 15 * 1024 ** 3
        usage = 0

    free = limit - usage
    # キャッシュは、アップロードや削除で手動に無効化するため、タイムアウトを長く設定（例: 1日）する
    cache.set(cache_key, free, 86400)
    return free

def get_total_free_storage():
    """
    登録されているすべてのGoogleアカウントの空き容量の合計をバイト単位で返す。
    """
    from .models import GoogleAccount  # 循環インポート回避のため関数内でインポート
    total_free = 0
    accounts = GoogleAccount.objects.all()
    for account in accounts:
        try:
            total_free += get_free_storage(account)
        except Exception as e:
            # 各アカウントで取得に失敗した場合は無視（またはログ出力）
            pass
    return total_free
