(function () {
    'use strict';

    function toast(message, level) {
        var stack = document.getElementById('toast-stack');
        if (!stack || !message) return;
        var el = document.createElement('div');
        el.className = 'alert alert-' + (level || 'success') + ' alert-dismissible fade show mb-0';
        el.setAttribute('role', 'alert');
        el.textContent = message;
        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn-close';
        close.setAttribute('data-bs-dismiss', 'alert');
        close.setAttribute('aria-label', 'Close');
        el.appendChild(close);
        stack.appendChild(el);
        setTimeout(function () { el.remove(); }, 4000);
    }

    // Auto-hide server-side messages
    document.querySelectorAll('#toast-stack .alert').forEach(function (el) {
        setTimeout(function () { el.remove(); }, 5000);
    });

    // Mood preset chips fill an input
    document.querySelectorAll('[data-fill]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = document.querySelector(btn.dataset.fill);
            if (!input) return;
            input.value = btn.dataset.value;
            input.focus();
            document.querySelectorAll('[data-fill="' + btn.dataset.fill + '"]').forEach(function (b) {
                b.classList.toggle('active', b === btn);
            });
        });
    });

    // Selects that submit their form on change (e.g. sort order)
    document.querySelectorAll('.js-autosubmit').forEach(function (el) {
        el.addEventListener('change', function () { el.form.submit(); });
    });

    // Spoilers: click to reveal
    document.querySelectorAll('.spoiler').forEach(function (el) {
        function reveal() { el.classList.add('revealed'); }
        el.addEventListener('click', reveal);
        el.addEventListener('keydown', function (e) { if (e.key === 'Enter') reveal(); });
    });

    function post(form, extra) {
        var data = new FormData(form);
        if (extra) Object.keys(extra).forEach(function (k) { data.set(k, extra[k]); });
        return fetch(form.action, {
            method: 'POST',
            body: data,
            headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
            credentials: 'same-origin'
        }).then(function (r) {
            return r.json().then(function (body) {
                if (!r.ok) throw new Error(body.message || 'Request failed');
                return body;
            });
        });
    }

    var ICONS = { watching: 'bi-play-fill', plan: 'bi-bookmark-fill', watched: 'bi-check2', '': 'bi-plus-lg' };
    var LABELS = { watching: 'Watching', plan: 'Plan', watched: 'Watched' };

    // Quick status buttons on cards (no page reload)
    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.classList.contains('js-status')) return;
        e.preventDefault();
        post(form).then(function (body) {
            var card = form.closest('.title-card');
            if (card) {
                var quick = card.querySelector('.quick');
                var icon = quick.querySelector('.btn i');
                icon.className = 'bi ' + ICONS[body.status || ''];
                quick.classList.toggle('has-status', !!body.status);
                quick.querySelectorAll('.dropdown-item').forEach(function (item) {
                    var f = item.closest('form');
                    var value = f.querySelector('[name=status]').value;
                    item.classList.toggle('active', !!body.status && value === body.status);
                });
                var meta = card.querySelector('.meta');
                var pill = meta.querySelector('.status-pill');
                if (body.status) {
                    if (!pill) { pill = document.createElement('span'); meta.appendChild(pill); }
                    pill.className = 'status-pill ' + body.status;
                    pill.textContent = LABELS[body.status];
                } else if (pill) {
                    pill.remove();
                }
            }
            toast(body.message, 'success');
        }).catch(function () { form.submit(); });
    });

    // Rating picker on detail pages
    document.querySelectorAll('.js-rate').forEach(function (form) {
        form.addEventListener('click', function (e) {
            var btn = e.target.closest('button[name=score]');
            if (!btn) return;
            e.preventDefault();
            post(form, { score: btn.value }).then(function (body) {
                form.querySelectorAll('button[name=score]').forEach(function (b) {
                    b.classList.toggle('selected', Number(b.value) <= Number(body.score));
                });
                var mine = document.querySelector('[data-my-score]');
                if (mine) {
                    mine.innerHTML = body.score + '<small class="fs-6 text-muted-mr">/10</small>';
                    if (mine.nextElementSibling) mine.nextElementSibling.textContent = 'rated';
                }
                var avg = document.querySelector('[data-community-avg]');
                if (avg && body.avg) avg.innerHTML = Number(body.avg).toFixed(1) + '<small class="fs-6 text-muted-mr">/10</small>';
                var count = document.querySelector('[data-community-count]');
                if (count) count.textContent = body.count + (body.count === 1 ? ' rating' : ' ratings');
                toast(body.message, 'success');
            }).catch(function () {
                var input = document.createElement('input');
                input.type = 'hidden'; input.name = 'score'; input.value = btn.value;
                form.appendChild(input);
                form.submit();
            });
        });
    });
})();
