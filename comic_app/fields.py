from django.db import models
from comic_app.storage import GoogleDriveStorage

class GoogleDriveImageField(models.ImageField):
    """
    Djangoのマイグレーションがstorageパラメータを直列化しないようにするカスタムフィールド。
    これにより、models.pyでstorageを明示しなくても済む。
    """

    def __init__(self, *args, **kwargs):
        # ここで常に GoogleDriveStorage を使うようにする
        kwargs['storage'] = GoogleDriveStorage()
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        # 親クラスのdeconstruct()から返される情報を受け取り、
        # storageがマイグレーションファイルに含まれないように削除する
        name, path, args, kwargs = super().deconstruct()
        if 'storage' in kwargs:
            del kwargs['storage']
        return name, path, args, kwargs
