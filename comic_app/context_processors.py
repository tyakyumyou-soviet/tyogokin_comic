from .google_drive_utils import get_total_free_storage

def free_storage(request):
    """
    スーパーユーザーの場合に、全Googleアカウントの空き容量の合計（GB単位）をコンテキストに追加する。
    """
    if request.user.is_superuser:
        total_free_bytes = get_total_free_storage()
        # バイトからギガバイトに変換（1GB = 1024^3 バイト）
        total_free_gb = total_free_bytes / (1024 ** 3)
        # 小数点以下2桁でフォーマット
        storage_str = f"{total_free_gb:.2f} GB"
    else:
        storage_str = ""
    return {'total_free_storage': storage_str}
