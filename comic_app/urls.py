from django.urls import path
from .views import ComicListView, ComicDetailView, file_manager, scrape_api, google_auth, add_google_account, google_account_list, upload_db_file, oauth2callback, remove_google_account,db_backup, ComicUpdateView, ComicDeleteView,UserListListView, UserListDetailView, UserListCreateView, UserListUpdateView, UserListDeleteView,TagListView, TagCreateView, TagDeleteView, search_comics,add_comic_to_multiple_lists



urlpatterns = [
    path('', ComicListView.as_view(), name='comic_list'),
    path('<int:pk>/', ComicDetailView.as_view(), name='comic_detail'),
    path('edit/<int:pk>/', ComicUpdateView.as_view(), name='comic_edit'),
    path('delete/<int:pk>/', ComicDeleteView.as_view(), name='comic_delete'),
    path('file-manager/', file_manager, name='file_manager'),
    path('scrape-api/', scrape_api, name='scrape_api'),
    path('google-auth/', google_auth, name='google_auth'),
    path('add-google-account/', add_google_account, name='add_google_account'),
    path('google-accounts/', google_account_list, name='google_account_list'),
    path('remove-google-account/<int:account_id>/', remove_google_account, name='remove_google_account'),
    path('upload-db-file/', upload_db_file, name='upload_db_file'),
    path('db-backup/', db_backup, name='db_backup'),
    path('oauth2callback/', oauth2callback, name='oauth2callback'),
    path('userlists/', UserListListView.as_view(), name='userlist_list'),
    path('userlists/<int:pk>/', UserListDetailView.as_view(), name='userlist_detail'),
    path('userlists/create/', UserListCreateView.as_view(), name='userlist_create'),
    path('userlists/<int:pk>/edit/', UserListUpdateView.as_view(), name='userlist_edit'),
    path('userlists/<int:pk>/delete/', UserListDeleteView.as_view(), name='userlist_delete'),
    path('tags/', TagListView.as_view(), name='tag_list'),
    path('tags/create/', TagCreateView.as_view(), name='tag_create'),
    path('tags/<int:pk>/delete/', TagDeleteView.as_view(), name='tag_delete'),
    path('search/', search_comics, name='search_comics'),
    path('<int:pk>/', ComicDetailView.as_view(), name='comic_detail'),
    path('<int:comic_pk>/add-to-multiple-lists/', add_comic_to_multiple_lists, name='add_comic_to_multiple_lists'),
]
