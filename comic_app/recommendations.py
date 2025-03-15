from django.db.models import Subquery, OuterRef, Value, IntegerField
from django.db.models.functions import Coalesce
from django.db.models import Count
from django.db.models import Q
import math

from .models import Tag, Comic, UserHistory

def recommend_for_user(user, limit=10):
    """
    ユーザーが最もよく閲覧した作品に含まれるタグを抽出し、
    それらのタグを持つ作品群を候補とする。

    さらに、各作品について:
      1) ユーザーのタグ嗜好ベクトル と 作品のタグベクトル の類似度（簡易コサイン類似度）
      2) ユーザーの閲覧回数 (user_view_count)

    これらを組み合わせたスコアを計算し、上位10件を返す。
    """

    # 1. ユーザーが多く閲覧している作品のタグを抽出する
    top_tags = Tag.objects.filter(comic__userhistory__user=user) \
                          .annotate(view_count=Count('comic__userhistory')) \
                          .order_by('-view_count')[:5]
    if not top_tags.exists():
        # ユーザーの履歴がないor極端に少ない場合のfallback
        return Comic.objects.none()

    # 2. ユーザーのタグ嗜好ベクトルを構築 (tag_id -> weight)
    #    -> よく閲覧している作品のタグは高い重み
    #    （ここでは: ユーザーが閲覧した作品の合計閲覧数をタグ別に合算）
    tag_weights = {}
    user_histories = UserHistory.objects.filter(user=user).select_related('comic')
    for hist in user_histories:
        count = hist.view_count
        # 作品に付与されているタグを取得
        for t in hist.comic.tags.all():
            tag_weights[t.id] = tag_weights.get(t.id, 0) + count

    if not tag_weights:
        # タグ嗜好が計算できない場合は何も返せない
        return Comic.objects.none()

    # 3. ユーザーがよく見るタグを含む作品を抽出（distinct）
    userhistory_sub = UserHistory.objects.filter(user=user, comic=OuterRef('pk')).values('view_count')[:1]
    candidate_comics_qs = (
        Comic.objects.filter(tags__in=top_tags)
        .distinct()
        .annotate(
            user_view_count=Coalesce(Subquery(userhistory_sub), Value(0), output_field=IntegerField())
        )
    )

    # 4. Python側で 「タグ類似度 + user_view_count」 を組み合わせてスコア計算
    #    DB から取り出した結果を一旦リスト化し、各作品にスコアを付与
    candidate_comics = list(candidate_comics_qs)

    # 先にユーザータグベクトルのノルムを計算 (コサイン類似度に使う)
    user_norm_sq = 0
    for w in tag_weights.values():
        user_norm_sq += w * w
    user_norm = math.sqrt(user_norm_sq) if user_norm_sq else 0.0

    def compute_score(comic):
        """1つの作品に対するスコアを計算する"""
        # (a) 作品のタグベクトル -> 該当タグがあれば1, なければ0
        comic_tag_ids = list(comic.tags.values_list('id', flat=True))
        if not comic_tag_ids:
            return 0.0

        # (b) コサイン類似度のためのドット積
        dot = 0
        for t_id, weight in tag_weights.items():
            if t_id in comic_tag_ids:
                dot += weight  # 作品側は重み=1とみなし

        comic_norm = math.sqrt(len(comic_tag_ids))  # 作品タグベクトルのノルム(単純にタグ数)

        if user_norm == 0 or comic_norm == 0:
            similarity = 0.0
        else:
            similarity = dot / (user_norm * comic_norm)

        # (c) ユーザーの閲覧回数を反映
        #     例: final_score = similarity / (1 + view_count)
        view_count = comic.user_view_count
        final_score = similarity / (1 + view_count)
        return final_score

    # 作品ごとにスコアを付与し、ソート
    scored = []
    for c in candidate_comics:
        s = compute_score(c)
        scored.append((c, s))

    # 例: スコア付与後に sort
    scored.sort(key=lambda x: x[1], reverse=True)
    recommended = [x[0] for x in scored[:limit]]

    return recommended
