# comic_app/exceptions.py
class StorageFullException(Exception):
    """Google Drive のすべてのアカウントの容量が満杯の場合に発生する例外"""
    pass
