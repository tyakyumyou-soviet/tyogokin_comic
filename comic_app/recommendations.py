from django.db.models import Subquery, OuterRef, Value, IntegerField
from django.db.models.functions import Coalesce
from django.db.models import Count
from .models import Tag, Comic, UserHistory

def recommend_for_user(user):
    """
    ユーザーが最もよく閲覧した作品に含まれるタグを抽出し、
    それらのタグを持つ作品群を取得。
    さらに、user_view_count (該当ユーザーがその作品を何回見たか) をアノテートし、
    昇順 (少ない回数) に並べて上位10件を返す。
    """
    # ユーザーが多く閲覧している作品のタグを抽出する
    top_tags = Tag.objects.filter(comic__userhistory__user=user)\
                          .annotate(view_count=Count('comic__userhistory'))\
                          .order_by('-view_count')[:5]
    if not top_tags.exists():
        # ユーザーの履歴が少ない場合などは、空か、適宜 fallback
        return Comic.objects.none()

    # ユーザーがよく見るタグを含む作品を抽出
    # その後、UserHistory から view_count をサブクエリで取り出し、
    # アノテート -> 並べ替え (少ない閲覧回数順)
    userhistory_sub = UserHistory.objects.filter(user=user, comic=OuterRef('pk')).values('view_count')[:1]

    recommended_comics = (
        Comic.objects.filter(tags__in=top_tags)
        .distinct()
        .annotate(
            user_view_count=Coalesce(Subquery(userhistory_sub), Value(0), output_field=IntegerField())
        )
        .order_by('user_view_count')[:10]  # 昇順 (少ない閲覧数順) で上から10件
    )
    return recommended_comics
