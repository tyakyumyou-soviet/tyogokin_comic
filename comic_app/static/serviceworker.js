// static/serviceworker.js

const CACHE_NAME = 'tyogokin-comic-v1';
const urlsToCache = [
  '/',  // オフライン時にも表示したいページを指定
  '/static/css/styles.css',
  // などなど、キャッシュしたいパスを必要に応じて追加
];

// インストール時にキャッシュを作成
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
});

// リクエスト取得時にキャッシュを参照
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      // キャッシュにあれば返す、なければネットワークに行く
      return response || fetch(event.request);
    })
  );
});
