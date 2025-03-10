import os
import tempfile
import logging
from django.core.files.storage import Storage
from django.core.cache import cache
from .google_drive_utils import upload_file_to_drive, get_free_storage, get_drive_service
from .exceptions import StorageFullException  # カスタム例外をインポート

logger = logging.getLogger(__name__)

class GoogleDriveStorage(Storage):
    def _save(self, name, content):
        logger.info(f"GoogleDriveStorage _save called for {name}")

        # 一時ファイルに書き出す
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(content.read())
        tmp.flush()
        tmp.close()

        # アップロードするファイルのサイズを計算
        file_size = os.path.getsize(tmp.name)
        logger.info(f"File size for upload: {file_size} bytes")

        # 登録されているすべてのGoogleアカウントを取得
        from .models import GoogleAccount  # 循環インポート回避のため
        google_accounts = list(GoogleAccount.objects.all())
        if not google_accounts:
            os.unlink(tmp.name)
            raise Exception("Googleアカウントが登録されていません。")

        uploaded_success = False
        file_id = None
        tried_accounts = []
        chosen_account = None  # ここで初期化

        for account in google_accounts:
            tried_accounts.append(account.email)

            # 1) アカウントの空き容量をチェック
            try:
                free = get_free_storage(account)
                logger.info(f"Account {account.email} free space: {free} bytes")
            except Exception as e:
                logger.error(f"Error checking storage for {account.email}: {str(e)}")
                continue

            # 2) 空き容量が足りているかチェック
            if free <= file_size:
                logger.info(f"Account {account.email} does not have enough space.")
                continue

            # 3) 実際にアップロードを試行
            try:
                result = upload_file_to_drive(tmp.name, name, account)
                file_id = result.get('id')
                if not file_id:
                    raise Exception("アップロード後のファイルIDが取得できませんでした。")
                logger.info(f"File uploaded to Google Drive with id: {file_id}")
                # 成功したので、選択されたアカウントを記録
                chosen_account = account
                uploaded_success = True
                break
            except Exception as e:
                err_msg = str(e)
                if "storageQuotaExceeded" in err_msg:
                    logger.warning(f"{account.email} -> storageQuotaExceeded. Trying next account.")
                    cache_key = f"free_storage_{account.id}"
                    cache.delete(cache_key)
                    continue
                else:
                    os.unlink(tmp.name)
                    raise Exception(f"アップロード中にエラーが発生しました: {err_msg}")

        if not uploaded_success:
            os.unlink(tmp.name)
            raise StorageFullException(f"すべてのGoogleアカウントの容量が満杯です。試行済み: {tried_accounts}")

        os.unlink(tmp.name)
        logger.info(f"File uploaded to Google Drive with id: {file_id}")
        if chosen_account is not None:
            cache.delete(f"free_storage_{chosen_account.id}")
        else:
            logger.error("Internal error: chosen_account is None after upload.")
        return file_id

    def delete(self, name):
        logger.info(f"GoogleDriveStorage delete called for {name}")
        from .models import GoogleAccount
        google_accounts = list(GoogleAccount.objects.all())
        if not google_accounts:
            logger.error("Googleアカウントが登録されていません。")
            return

        deletion_succeeded = False
        for account in google_accounts:
            try:
                drive_service = get_drive_service(account)
                drive_service.files().delete(fileId=name).execute()
                logger.info(f"File {name} deleted from Google Drive using account {account.email}")
                deletion_succeeded = True
                cache.delete(f"free_storage_{account.id}")
                break
            except Exception as e:
                logger.error(f"Error deleting file {name} with account {account.email}: {str(e)}")
                continue

        if not deletion_succeeded:
            logger.error(f"Failed to delete file {name} from all accounts.")

    def exists(self, name):
        return False

    def url(self, name):
        return f"https://lh3.googleusercontent.com/d/{name}"
