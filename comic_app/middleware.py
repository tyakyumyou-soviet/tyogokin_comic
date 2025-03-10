# comic_app/middleware.py
from django.shortcuts import render
import logging

logger = logging.getLogger(__name__)

class GenericErrorMiddleware:
    """
    アプリ全体でキャッチされなかった例外を補足し、
    「エラーが発生しました。最初からやり直してください。」というメッセージを表示するエラーページへ遷移させます。
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # ログに例外を記録
            logger.exception("Unhandled exception caught by GenericErrorMiddleware")
            # 未処理の例外が発生した場合、独自のエラーページをレンダリング
            return render(request, "comic_app/generic_error.html", {
                "message": "エラーが発生しました。最初からやり直してください。"
            }, status=500)
