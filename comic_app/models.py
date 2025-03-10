from django.db import models
from comic_app.storage import GoogleDriveStorage
from django.core.files.storage import default_storage
from django.conf import settings
from comic_app.fields import GoogleDriveImageField
from django.dispatch import receiver
from django.db.models.signals import post_delete

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Comic(models.Model):
    title = models.CharField(max_length=255)
    #thumbnail = models.ImageField(upload_to='thumbnails/', storage=GoogleDriveStorage())
    #thumbnail = models.ImageField(upload_to='thumbnails/')
    thumbnail = GoogleDriveImageField(upload_to='thumbnails/')
    # 作品にタグを付与する（作品編集画面で変更可能）
    tags = models.ManyToManyField(Tag, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_thumbnail_url(self):
        """
        サムネイル画像用のURLを生成します。  
        この例では、保存されている値（Google Drive のファイルID）を利用して、  
        https://drive.google.com/thumbnail?id={file_id} の形式で返します。
        """
        file_id = self.thumbnail.name  # DBに保存された値はファイルIDになっていると仮定
        return f"https://drive.google.com/thumbnail?id={file_id}"


@receiver(post_delete, sender=Comic)
def delete_comic_thumbnail(sender, instance, **kwargs):
    """
    Comic インスタンス削除時に、thumbnail に保存されているファイルも削除する。
    カスタムストレージが設定されている場合、instance.thumbnail.delete() を呼ぶと、
    GoogleDriveStorage.delete() が実行されます。
    """
    if instance.thumbnail:
        instance.thumbnail.delete(save=False)


class ComicImage(models.Model):
    comic = models.ForeignKey(Comic, on_delete=models.CASCADE, related_name='images')
    # storage を明示的に指定
    #image = models.ImageField(upload_to='detail_images/', storage=GoogleDriveStorage())
    #image = models.ImageField(upload_to='detail_images/')
    image = GoogleDriveImageField(upload_to='detail_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.comic.title} - {self.id}"

@receiver(post_delete, sender=ComicImage)
def delete_comic_image_file(sender, instance, **kwargs):
    # 明示的にストレージの delete() を呼ぶ
    if instance.image:
        instance.image.delete(save=False)


class UserHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comic = models.ForeignKey(Comic, on_delete=models.CASCADE)
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.comic.title} ({self.view_count})"


class GoogleAccount(models.Model):
    email = models.EmailField(unique=True)  # Googleアカウントのメールアドレス
    credentials_json = models.TextField()  # OAuth認証情報（JSON文字列として保存）

    def __str__(self):
        return self.email

class DBBackupLog(models.Model):
    backup_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Backup on {self.backup_date}"


class UserList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_lists')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    # サムネイルは任意で設定可能。自動で設定したい場合は、テンプレートまたはプロパティで対応します。
    thumbnail = models.ImageField(upload_to='list_thumbnails/', blank=True, null=True)
    # お気に入りの作品（Comicモデルとの多対多）
    comics = models.ManyToManyField('Comic', related_name='lists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    @property
    def display_thumbnail_url(self):
        """
        自動でリストのサムネイル画像を返します。
        ・まず、thumbnailフィールドに値があるならそれを使い、
        ・なければ、リストに登録されている一番最初の作品のサムネイルを利用します。
        """
        if self.thumbnail:
            return self.thumbnail.url
        first_comic = self.comics.first()
        if first_comic and first_comic.thumbnail:
            return first_comic.thumbnail.url
        return ''  # 必要に応じてデフォルト画像のURLを返す


