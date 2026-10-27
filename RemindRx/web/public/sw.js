/* RemindRx service worker: offline app shell + notification clicks.
 * Network-first for pages (so updates arrive), cache-first for hashed build
 * assets. The app makes no API calls, so there is nothing else to intercept. */
const CACHE = 'remindrx-v1';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon.svg', '/icon-192.png', '/icon-512.png'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(() => undefined));
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()),
    );
});

self.addEventListener('fetch', e => {
    const req = e.request;
    if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
    const url = new URL(req.url);
    if (url.pathname.startsWith('/assets/')) {
        e.respondWith(
            caches.match(req).then(hit => hit || fetch(req).then(res => {
                const copy = res.clone();
                caches.open(CACHE).then(c => c.put(req, copy));
                return res;
            })),
        );
        return;
    }
    e.respondWith(
        fetch(req)
            .then(res => {
                if (res.ok && (req.mode === 'navigate' || SHELL.includes(url.pathname))) {
                    const copy = res.clone();
                    caches.open(CACHE).then(c => c.put(req.mode === 'navigate' ? '/' : req, copy));
                }
                return res;
            })
            .catch(() => caches.match(req.mode === 'navigate' ? '/' : req)),
    );
});

self.addEventListener('notificationclick', e => {
    e.notification.close();
    e.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
            const open = list.find(c => 'focus' in c);
            return open ? open.focus() : self.clients.openWindow('/');
        }),
    );
});
