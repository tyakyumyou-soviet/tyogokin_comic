import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


from django.views.generic import ListView, DetailView
from .models import Comic
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ComicUploadForm
from .models import Comic, ComicImage, DBBackupLog

import re
import requests
import base64
from django.core.files.base import ContentFile
from .forms import ScrapeImagesForm

import json
from google_auth_oauthlib.flow import Flow
from .models import GoogleAccount
from .forms import GoogleAccountForm
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from django.http import JsonResponse

from django.conf import settings
from django.contrib import messages
from .google_drive_utils import upload_file_to_drive

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from django.urls import reverse_lazy
from django.views.generic import UpdateView, DeleteView

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView
from .models import UserList

from .exceptions import StorageFullException

from .models import UserHistory
from .recommendations import recommend_for_user

from django.utils import timezone

from .models import Tag

from .forms import ComicUpdateForm

from datetime import date, datetime, timedelta
from django.core.cache import cache
import random

from django.db.models import Q


def search_comics(request):
    query = request.GET.get('q', '')
    results = Comic.objects.none()
    if query:
        # 半角・全角スペースで区切って、各キーワードを抽出する
        keywords = re.split(r'[\s　]+', query.strip())
        # 複数のキーワードのOR検索条件を構築
        q_objects = Q()
        for word in keywords:
            if word:  # 空文字は無視
                q_objects |= Q(title__icontains=word) | Q(tags__name__icontains=word)
        results = Comic.objects.filter(q_objects).distinct()
    context = {
        'query': query,
        'results': results
    }
    return render(request, 'comic_app/search_results.html', context)


class ComicListView(LoginRequiredMixin,ListView):
    model = Comic
    template_name = 'comic_app/comic_list.html'
    context_object_name = 'comics'

    ordering = ['-id']

    paginate_by = 5  # 1ページあたり20件表示

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        cache_key = f"today_recommended_{today}"
        # キャッシュから今日のおすすめのComic IDリストを取得（リスト形式）
        recommended_ids = cache.get(cache_key)
        if recommended_ids:
            today_recommended = Comic.objects.filter(pk__in=recommended_ids)
        else:
            comics = list(Comic.objects.all())
            if comics:
                # 今日の日付をシードにしてランダムサンプルを取得（最大2件）
                random.seed(today.toordinal())
                today_recommended = random.sample(comics, min(2, len(comics)))
                # 明日の午前0時までの秒数をTTLに設定
                now = datetime.now()
                tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
                ttl = (tomorrow - now).total_seconds()
                # 選出された作品のIDリストをキャッシュに保存
                cache.set(cache_key, [comic.pk for comic in today_recommended], ttl)
            else:
                today_recommended = []
        context['today_recommended'] = today_recommended

        if self.request.user.is_authenticated:
            context['recommended_comics'] = recommend_for_user(self.request.user)
        else:
            context['recommended_comics'] = None
        return context


def add_comic_to_multiple_lists(request, comic_pk):
    if request.method == 'POST':
        comic = get_object_or_404(Comic, pk=comic_pk)
        userlists = UserList.objects.filter(user=request.user)
        selected_list_ids = request.POST.getlist('userlist_ids')  # 選択されたものだけ
        
        for ul in userlists:
            if str(ul.id) in selected_list_ids:
                # チェックが付いている → 登録がなければ追加
                ul.comics.add(comic)
            else:
                # チェックが外されている → 登録済みなら解除
                if comic in ul.comics.all():
                    ul.comics.remove(comic)
        
        messages.success(request, "マイリストの登録状態を更新しました。")
    return redirect('comic_detail', pk=comic_pk)

class ComicDetailView(DetailView):
    model = Comic
    template_name = 'comic_app/comic_detail.html'
    context_object_name = 'comic'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # 閲覧履歴の記録
        if request.user.is_authenticated:
            comic = self.get_object()
            history, created = UserHistory.objects.get_or_create(user=request.user, comic=comic)
            history.view_count += 1
            history.last_viewed = timezone.now()
            history.save()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            userlists = UserList.objects.filter(user=self.request.user)

            # 作品が既に登録されているマイリストのIDを取得
            comic = self.object  # DetailViewでは self.object が現在のComic
            # 例： 多対多:  userlist.comics
            list_ids_already_registered = userlists.filter(comics=comic).values_list('id', flat=True)

            context['userlists'] = userlists
            # 既に登録されているリストのIDのリストをセット
            context['list_ids_already_registered'] = list(list_ids_already_registered)
        else:
            context['userlists'] = None
            context['list_ids_already_registered'] = []
        return context

class ComicUpdateView(UpdateView):
    model = Comic
    #fields = ['title', 'thumbnail']  # 必要に応じて編集可能なフィールドを指定
    form_class = ComicUpdateForm
    template_name = 'comic_app/comic_edit.html'
    success_url = reverse_lazy('comic_list')

class ComicDeleteView(DeleteView):
    model = Comic
    template_name = 'comic_app/comic_confirm_delete.html'
    success_url = reverse_lazy('comic_list')


def upload_comic(request):
    if request.method == 'POST':
        form = ComicUploadForm(request.POST, request.FILES)
        if form.is_valid():
            comic = form.save()
            detail_images = request.FILES.getlist('detail_images')
            for image_file in detail_images:
                ComicImage.objects.create(
                    comic=comic,
                    image=image_file
                )
            return redirect('comic_list')
    else:
        form = ComicUploadForm()
    return render(request, 'comic_app/comic_upload.html', {'form': form})



def file_manager(request):
    from .models import Tag  # GET 時にタグ一覧を渡すためのインポート
    if request.method == 'POST':
        # 完全アップロード（最終確定）時の処理
        title = request.POST.get('title')
        image_count = int(request.POST.get('image_count', '0'))
        selected_images = []
        for i in range(image_count):
            # 各画像が送信される hidden input を利用
            if request.POST.get(f'selected_{i}') == 'on':
                base64_data = request.POST.get(f'image_{i}')
                filename = request.POST.get(f'filename_{i}')
                selected_images.append({'base64': base64_data, 'filename': filename})
        # タグ選択値を取得（複数選択の場合は getlist を使用）
        selected_tag_ids = request.POST.getlist('tags')
        
        if title and selected_images:
            try:
                # Comic 作成（サムネイルは先頭の画像を利用）
                first_image = selected_images[0]
                comic = Comic.objects.create(
                    title=title,
                    thumbnail=ContentFile(base64.b64decode(first_image['base64']), name=first_image['filename'])
                )
                # 選択されたタグがあれば、Comic に紐付ける
                if selected_tag_ids:
                    comic.tags.set(selected_tag_ids)
                for img in selected_images:
                    ComicImage.objects.create(
                        comic=comic,
                        image=ContentFile(base64.b64decode(img['base64']), name=img['filename'])
                    )
            except StorageFullException as e:
                # 容量不足の場合は独自エラーページを表示
                return render(request, "comic_app/storage_full_error.html", {"error_message": str(e)})
            except Exception as e:
                err_msg = str(e)
                if "再認証" in err_msg:
                    return render(request, "comic_app/re_authentication_required.html", {"error_message": err_msg})
                else:
                    messages.error(request, f"アップロードエラー: {err_msg}")
                    return redirect('file_manager')
            return redirect('comic_list')
        else:
            error = "タイトルと少なくとも1つの画像を選択してください。"
            # GET 時に渡すタグ一覧も再利用する
            tags = Tag.objects.all()
            return render(request, 'comic_app/file_manager.html', {'error': error, 'scrape_form': ScrapeImagesForm(), 'tags': tags})
    else:
        # GET: 空のUI表示。タグ一覧をテンプレートに渡す
        tags = Tag.objects.all()
        return render(request, 'comic_app/file_manager.html', {'scrape_form': ScrapeImagesForm(), 'tags': tags})


def scrape_api(request):
    """AJAX用のスクレイピングAPI：POSTで base_url と count を受け取り、画像情報（base64, filename）を返す"""
    if request.method == 'POST':
        base_url = request.POST.get('base_url')
        count = int(request.POST.get('count', 0))
        match = re.search(r'(.*?)(\d+)(\.\w+)$', base_url)
        if not match:
            return JsonResponse({'error': 'URL形式が正しくありません。'})
        prefix, number_str, extension = match.groups()
        start_number = int(number_str)
        width = len(number_str)
        scraped_images = []
        for i in range(start_number, start_number + count):
            url = f"{prefix}{i:0{width}d}{extension}"
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    img_base64 = base64.b64encode(response.content).decode('utf-8')
                    scraped_images.append({
                        'base64': img_base64,
                        'filename': f"{i:0{width}d}{extension}"
                    })
            except Exception as e:
                continue
        return JsonResponse({'scraped_images': scraped_images})
    return JsonResponse({'error': 'Invalid request'}, status=400)






# Google APIのスコープ（Driveにファイルをアップロードできる権限）
#SCOPES = ['https://www.googleapis.com/auth/drive.file']
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',  # もしくは 'email'
    'https://www.googleapis.com/auth/drive.file'
]

def add_google_account(request):
    """Googleアカウントを追加するビュー"""
    if request.method == 'POST':
        form = GoogleAccountForm(request.POST)
        if form.is_valid():
            credentials_json = form.cleaned_data['credentials_json']
            credentials_data = json.loads(credentials_json)
            email = credentials_data.get('client_email')

            if GoogleAccount.objects.filter(email=email).exists():
                return JsonResponse({'error': 'このアカウントは既に登録されています。'})

            GoogleAccount.objects.create(email=email, credentials_json=credentials_json)
            return redirect('google_account_list')

    return render(request, 'comic_app/add_google_account.html')

def google_auth(request):
    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, 'client_secret.json'),
        scopes=SCOPES,
        #redirect_uri=request.build_absolute_uri('/oauth2callback/')
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI  # 環境変数を利用
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    request.session['state'] = state
    return redirect(authorization_url)

def oauth2callback(request):
    state = request.session.get('state')
    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, 'client_secret.json'),
        scopes=SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials

    # credentials.id_token は文字列なので、デコードする
    request_adapter = google_requests.Request()
    try:
        decoded_token = google_id_token.verify_oauth2_token(credentials.id_token, request_adapter)
        email = decoded_token.get('email', 'unknown@example.com')
    except Exception as e:
        email = 'unknown@example.com'
    
    GoogleAccount.objects.update_or_create(
        email=email,
        defaults={'credentials_json': credentials.to_json()}
    )
    return redirect('google_account_list')

def google_account_list(request):
    accounts = GoogleAccount.objects.all()
    return render(request, 'comic_app/google_account_list.html', {'accounts': accounts})





def upload_db_file(request):
    """
    DBファイル（db.sqlite3）をGoogle Driveにアップロードするビュー。
    登録されているGoogleAccountの中から、アップロードするファイルサイズ分の空き容量があるアカウントを選択します。
    """
    from .models import GoogleAccount  # 必要に応じてインポート
    google_accounts = list(GoogleAccount.objects.all())
    if not google_accounts:
        messages.error(request, "Googleアカウントが登録されていません。先に登録してください。")
        return redirect('google_account_list')

    db_file_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
    try:
        file_size = os.path.getsize(db_file_path)
    except Exception as e:
        messages.error(request, f"DBファイルのサイズ取得に失敗しました: {str(e)}")
        return redirect('comic_list')

    chosen_account = None
    tried_accounts = []
    for account in google_accounts:
        tried_accounts.append(account.email)
        try:
            free = get_free_storage(account)
            logger.info(f"Account {account.email} free space: {free} bytes")
        except Exception as e:
            logger.error(f"Error checking storage for {account.email}: {str(e)}")
            continue

        if free > file_size:
            chosen_account = account
            break

    if chosen_account is None:
        messages.error(request, f"すべてのGoogleアカウントの容量が満杯です。試行済み: {tried_accounts}")
        return redirect('comic_list')

    try:
        result = upload_file_to_drive(db_file_path, 'db.sqlite3', chosen_account)
        # キャッシュ削除など、必要であればここで chosen_account のキャッシュも無効化する
        messages.success(request, f"DBファイルをアップロードしました。File ID: {result.get('id')}")
    except Exception as e:
        messages.error(request, f"アップロードに失敗しました: {str(e)}")
    return redirect('comic_list')

def remove_google_account(request, account_id):
    account = get_object_or_404(GoogleAccount, id=account_id)
    account.delete()
    return redirect('google_account_list')


def db_backup(request):
    # これまでのバックアップ実績を取得
    backup_logs = DBBackupLog.objects.all().order_by('-backup_date')
    last_backup = backup_logs.first() if backup_logs.exists() else None
    backup_count = backup_logs.count()

    if request.method == "POST":
        # Googleアカウントが登録されているかチェック
        google_accounts = GoogleAccount.objects.all()
        if not google_accounts.exists():
            messages.error(request, "Googleアカウントが登録されていません。先に登録してください。")
            return redirect('google_account_list')
        
        google_account = google_accounts.first()  # シンプルな実装：最初のアカウントを使用
        
        # DBファイルのパスを指定（通常はプロジェクトのルートにあるdb.sqlite3）
        db_file_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        try:
            result = upload_file_to_drive(db_file_path, 'db.sqlite3', google_account)
            # アップロード成功時、バックアップログを記録する
            DBBackupLog.objects.create()
            messages.success(request, f"DBファイルをアップロードしました。File ID: {result.get('id')}")
        except Exception as e:
            messages.error(request, f"アップロードに失敗しました: {str(e)}")
        return redirect('db_backup')

    # GETの場合、バックアップ情報と実行ボタンを表示
    return render(request, 'comic_app/db_backup.html', {
        'last_backup': last_backup,
        'backup_count': backup_count,
    })



class UserListListView(LoginRequiredMixin, ListView):
    model = UserList
    template_name = 'comic_app/userlist_list.html'
    context_object_name = 'userlists'

    def get_queryset(self):
        #return UserList.objects.filter(user=self.request.user)
        return UserList.objects.filter(user=self.request.user).order_by('-updated_at')

class UserListDetailView(LoginRequiredMixin, DetailView):
    model = UserList
    template_name = 'comic_app/userlist_detail.html'
    context_object_name = 'userlist'
    
    def get_queryset(self):
        return UserList.objects.filter(user=self.request.user)

class UserListCreateView(LoginRequiredMixin, CreateView):
    model = UserList
    fields = ['name', 'description', 'thumbnail', 'comics']
    template_name = 'comic_app/userlist_form.html'
    success_url = reverse_lazy('userlist_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class UserListUpdateView(LoginRequiredMixin, UpdateView):
    model = UserList
    fields = ['name', 'description', 'thumbnail', 'comics']
    template_name = 'comic_app/userlist_form.html'
    success_url = reverse_lazy('userlist_list')
    
    def get_queryset(self):
        return UserList.objects.filter(user=self.request.user)

class UserListDeleteView(LoginRequiredMixin, DeleteView):
    model = UserList
    template_name = 'comic_app/userlist_confirm_delete.html'
    success_url = reverse_lazy('userlist_list')
    
    def get_queryset(self):
        return UserList.objects.filter(user=self.request.user)


class TagListView(ListView):
    model = Tag
    template_name = 'comic_app/tag_list.html'
    context_object_name = 'tags'

    ordering = ['-id']

class TagCreateView(CreateView):
    model = Tag
    fields = ['name']
    template_name = 'comic_app/tag_form.html'
    success_url = reverse_lazy('tag_list')

class TagDeleteView(DeleteView):
    model = Tag
    template_name = 'comic_app/tag_confirm_delete.html'
    success_url = reverse_lazy('tag_list')

def custom_404(request, exception):
    return render(request, "404.html", status=404)