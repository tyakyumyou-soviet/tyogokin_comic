from django.test import TestCase
from django.urls import reverse
from .models import GoogleAccount, Comic
import json
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from .google_drive_utils import upload_file_to_drive
from unittest.mock import patch

class ComicAppTests(TestCase):

    def test_home_page_status_code(self):
        """ホームページ（Comic一覧画面）が正常にロードされるかテスト"""
        url = reverse('comic_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_file_manager_page_status_code(self):
        """ファイルマネージャUIのページが正常にロードされるかテスト"""
        url = reverse('file_manager')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_google_account_list_status_code(self):
        """Googleアカウント管理ページが正常にロードされるかテスト"""
        url = reverse('google_account_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)




class GoogleAccountTests(TestCase):

    def test_google_account_creation(self):
        """Googleアカウントをデータベースに登録できるかテスト"""
        google_account = GoogleAccount.objects.create(
            email="testuser@gmail.com",
            credentials_json=json.dumps({"access_token": "dummy_token"})
        )
        self.assertEqual(GoogleAccount.objects.count(), 1)
        self.assertEqual(google_account.email, "testuser@gmail.com")
        
        
        
class FileUploadTests(TestCase):
    
    def test_comic_creation_with_thumbnail(self):
        """Comicモデルの作成時にサムネイルが保存されるかテスト"""
        image = SimpleUploadedFile("thumbnail.jpg", b"file_content", content_type="image/jpeg")
        comic = Comic.objects.create(title="Test Comic", thumbnail=image)
        self.assertEqual(Comic.objects.count(), 1)
        self.assertTrue(os.path.exists(comic.thumbnail.path))



class GoogleDriveUploadTests(TestCase):

    @patch('comic_app.google_drive_utils.get_drive_service')
    def test_upload_file_to_drive(self, mock_get_drive_service):
        """Google Driveへのファイルアップロードが正常に呼び出されるかテスト"""
        google_account = GoogleAccount.objects.create(
            email="testuser@gmail.com",
            credentials_json="{}"
        )
        mock_drive_service = mock_get_drive_service.return_value
        mock_drive_service.files().create().execute.return_value = {"id": "test_file_id"}

        result = upload_file_to_drive("db.sqlite3", "test_db_backup.sqlite3", google_account)
        
        self.assertEqual(result["id"], "test_file_id")
