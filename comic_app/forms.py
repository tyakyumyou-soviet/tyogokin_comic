from django import forms
from .models import Comic

# カスタムウィジェットを先に定義する
class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        final_attrs = {'multiple': True}
        if attrs:
            final_attrs.update(attrs)
        super().__init__(attrs=final_attrs)

# フォーム定義
class ComicUploadForm(forms.Form):
    #title = forms.CharField(max_length=255, label="タイトル")
    #thumbnail = forms.ImageField(label="サムネイル画像")
    detail_images = forms.ImageField(
        widget=MultiFileInput(),
        label="詳細画像（複数選択可）",
        required=False
    )
    class Meta:
        model = Comic
        # Comicモデルには 'title', 'thumbnail', 'tags' があると想定
        fields = ['title', 'thumbnail', 'tags']
        widgets = {
            'tags': forms.CheckboxSelectMultiple(),  # 複数選択可能なチェックボックスでタグを選ぶ
        }

class ScrapeImagesForm(forms.Form):
    base_url = forms.URLField(label="ベースURL (例: https://example.com/001.jpg)")
    count = forms.IntegerField(label="枚数", min_value=1)

class GoogleAccountForm(forms.Form):
    credentials_json = forms.CharField(widget=forms.HiddenInput())

# 作品編集用フォームも同様に定義する
class ComicUpdateForm(forms.ModelForm):
    detail_images = forms.ImageField(
        widget=MultiFileInput(),
        label="詳細画像（複数選択可）",
        required=False
    )
    class Meta:
        model = Comic
        fields = ['title', 'thumbnail', 'tags']
        widgets = {
            'tags': forms.CheckboxSelectMultiple(),
        }
