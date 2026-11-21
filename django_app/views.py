import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from . import ai, tmdb
from .context_processors import CATEGORY_NAV
from .forms import (CatalogFilterForm, ProfileUpdateForm, RegisterForm, ReviewForm,
                    UserListForm)
from .models import (Cinematography, Genre, Rating, Review, UserList, WatchlistEntry,
                     profile as Profile)

logger = logging.getLogger(__name__)

PAGE_SIZE = 24
CATEGORY_SLUGS = {slug: key for slug, key, _ in CATEGORY_NAV}
CATEGORY_TITLES = {key: label for _, key, label in CATEGORY_NAV}
SORTS = {
    'popular': [F('popularity').desc(), F('tmdb_vote_count').desc(), '-id'],
    'rating': [F('tmdb_rating').desc(nulls_last=True), F('tmdb_vote_count').desc(), '-id'],
    'user_rating': [F('user_avg').desc(nulls_last=True), F('tmdb_rating').desc(nulls_last=True), '-id'],
    'newest': ['-release_date', '-id'],
    'oldest': ['release_date', 'id'],
    'title': ['title', 'id'],
}


# --------------------------------------------------------------------------- helpers

def _safe_next(request, default):
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return default


def _wants_json(request):
    return (request.headers.get('x-requested-with') == 'fetch'
            or 'application/json' in request.headers.get('accept', ''))


def _respond(request, item, message, payload, level=messages.SUCCESS, status=200):
    if _wants_json(request):
        return JsonResponse({'ok': status == 200, 'message': message, **payload}, status=status)
    messages.add_message(request, level, message)
    return redirect(_safe_next(request, item.get_absolute_url() if item else reverse('django_app:home')))


def _user_state(user, item_ids):
    """Statuses and ratings of the current user for a page of titles (2 queries)."""
    if not user.is_authenticated or not item_ids:
        return {}, {}
    statuses = dict(WatchlistEntry.objects.filter(user=user, item_id__in=item_ids)
                    .values_list('item_id', 'status'))
    ratings = dict(Rating.objects.filter(user=user, item_id__in=item_ids).values_list('item_id', 'score'))
    return statuses, ratings


def _text_search(qs, query):
    # SQLite's LIKE is case-insensitive for ASCII only, so try common casings too (Cyrillic etc.).
    variants = {query, query.lower(), query.upper(), query.capitalize(), query.title()}
    cond = Q()
    for v in variants:
        cond |= Q(title__contains=v) | Q(original_title__contains=v)
    return qs.filter(cond | Q(title__icontains=query) | Q(original_title__icontains=query))


def apply_filters(qs, data):
    if data.get('category'):
        qs = qs.filter(category=data['category'])
    genres = data.get('genres') or []
    if genres:
        if data.get('genre_mode') == 'all':
            for slug in genres:
                qs = qs.filter(genres__slug=slug)
        else:
            qs = qs.filter(genres__slug__in=genres).distinct()
    if data.get('q'):
        qs = _text_search(qs, data['q'].strip())
    if data.get('year_from'):
        qs = qs.filter(release_date__year__gte=data['year_from'])
    if data.get('year_to'):
        qs = qs.filter(release_date__year__lte=data['year_to'])
    if data.get('min_rating') is not None:
        qs = qs.filter(tmdb_rating__gte=data['min_rating'])
    return qs


def _page_items(paginator_page, ids_mode):
    if not ids_mode:
        return list(paginator_page.object_list)
    ids = list(paginator_page.object_list)
    objs = Cinematography.objects.in_bulk(ids)
    return [objs[i] for i in ids if i in objs]


# --------------------------------------------------------------------------- catalogue

def home(request):
    # Old bookmarked filter URLs (/home?cinematography=…&genre=…) keep working.
    legacy = {k: request.GET.get(k) for k in ('cinematography', 'genre', 'interests', 'mood')}
    if any(legacy.values()):
        params = {'category': legacy['cinematography'] if legacy['cinematography'] != 'none' else '',
                  'genres': legacy['genre'] if legacy['genre'] != 'none' else '',
                  'interests': legacy['interests'] or '', 'mood': legacy['mood'] or ''}
        return redirect(f"{reverse('django_app:catalog')}?{urlencode({k: v for k, v in params.items() if v})}")

    base = Cinematography.objects.order_by(*SORTS['popular'])
    sections = []
    for slug, key, label in CATEGORY_NAV:
        items = list(base.filter(category=key)[:12])
        if items:
            sections.append({'title': f'Popular {label.lower()}', 'items': items,
                             'url': reverse('django_app:catalog_category', args=[slug])})
    top_rated = list(Cinematography.objects.filter(tmdb_vote_count__gte=50)
                     .order_by(*SORTS['rating'])[:12])
    if top_rated:
        sections.append({'title': 'Top rated on TMDB', 'items': top_rated,
                         'url': f"{reverse('django_app:catalog')}?sort=rating"})
    community = list(Cinematography.objects.with_user_stats().filter(user_votes__gt=0)
                     .order_by(F('user_avg').desc(), '-user_votes')[:12])
    if community:
        sections.append({'title': 'Loved by our community', 'items': community,
                         'url': f"{reverse('django_app:catalog')}?sort=user_rating"})

    all_ids = [i.id for s in sections for i in s['items']]
    statuses, ratings = _user_state(request.user, all_ids)
    return render(request, 'django_app/home.html', {
        'sections': sections,
        'statuses': statuses,
        'ratings': ratings,
        'total_titles': Cinematography.objects.count(),
        'genres': Genre.objects.filter(titles__isnull=False).distinct(),
    })


def catalog(request, category_slug=None):
    data = request.GET.copy()
    forced_category = None
    if category_slug:
        forced_category = CATEGORY_SLUGS.get(category_slug)
        if not forced_category:
            raise Http404('Unknown category')
        data['category'] = forced_category
    # Accept comma-separated genres too (?genres=action,drama).
    if len(data.getlist('genres')) == 1 and ',' in data.get('genres', ''):
        data.setlist('genres', [g for g in data['genres'].split(',') if g])

    form = CatalogFilterForm(data)
    form.is_valid()
    cleaned = form.cleaned_data  # invalid fields are simply ignored

    qs = apply_filters(Cinematography.objects.all(), cleaned)
    interests, mood = cleaned.get('interests', ''), cleaned.get('mood', '')
    sort = cleaned.get('sort') or ''
    recommendation = None
    ids_mode = False

    if (interests or mood) and sort in ('', 'relevance'):
        filters_key = urlencode(sorted((k, v) for k, v in data.lists() if k not in ('page',)), doseq=True)
        recommendation = ai.recommend(qs, interests, mood, filters_key=filters_key)
        source = recommendation.ids
        ids_mode = True
        sort = 'relevance'
    else:
        sort = sort if sort in SORTS else 'popular'
        if sort == 'user_rating':
            qs = qs.with_user_stats()
        source = qs.order_by(*SORTS[sort])

    paginator = Paginator(source, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    items = _page_items(page_obj, ids_mode)
    statuses, ratings = _user_state(request.user, [i.id for i in items])

    params = request.GET.copy()
    params.pop('page', None)
    active_filters = any(cleaned.get(k) for k in ('q', 'genres', 'year_from', 'year_to', 'interests', 'mood')) \
        or cleaned.get('min_rating') is not None or (cleaned.get('category') and not forced_category)

    return render(request, 'django_app/catalog.html', {
        'form': form,
        'items': items,
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1),
        'query_string': params.urlencode(),
        'statuses': statuses,
        'ratings': ratings,
        'recommendation': recommendation,
        'current_sort': sort,
        'selected_genres': cleaned.get('genres') or [],
        'category': forced_category or cleaned.get('category') or '',
        'category_slug': category_slug,
        'page_title': CATEGORY_TITLES.get(forced_category, 'Browse all titles'),
        'active_filters': active_filters,
        'clear_url': request.path,
    })


def all_movies(request):
    return redirect('django_app:catalog_category', category_slug='movies')


def title_detail(request, pk):
    item = get_object_or_404(Cinematography.objects.prefetch_related('genres'), pk=pk)
    stats = item.ratings.aggregate(avg=Avg('score'), count=Count('id'))
    reviews_qs = item.reviews.select_related('user', 'user__profile')
    review_page = Paginator(reviews_qs, 10).get_page(request.GET.get('rpage'))
    author_scores = dict(item.ratings.filter(user_id__in=[r.user_id for r in review_page])
                         .values_list('user_id', 'score'))

    genre_ids = [g.id for g in item.genres.all()]
    similar = (Cinematography.objects.filter(genres__in=genre_ids).exclude(pk=item.pk)
               .annotate(shared=Count('genres', filter=Q(genres__in=genre_ids)))
               .order_by('-shared', F('popularity').desc(), '-id')[:12]) if genre_ids else \
        Cinematography.objects.filter(category=item.category).exclude(pk=item.pk).order_by(*SORTS['popular'])[:12]
    similar = list(similar)

    ctx = {
        'item': item,
        'stats': stats,
        'reviews': review_page,
        'author_scores': author_scores,
        'similar': similar,
        'details': tmdb.title_details(item),
        'status_choices': WatchlistEntry.STATUS_CHOICES,
        'score_range': range(1, 11),
    }
    statuses, ratings = _user_state(request.user, [item.id] + [s.id for s in similar])
    ctx.update(statuses=statuses, ratings=ratings)
    if request.user.is_authenticated:
        my_review = item.reviews.filter(user=request.user).first()
        ctx.update(
            my_status=statuses.get(item.id, ''),
            my_score=ratings.get(item.id),
            my_review=my_review,
            review_form=ReviewForm(instance=my_review),
            my_lists=request.user.lists.annotate(
                has_item=Count('items', filter=Q(items=item))).order_by('name'),
            list_form=UserListForm(user=request.user),
        )
    return render(request, 'django_app/detail.html', ctx)


# --------------------------------------------------------------------------- user actions

@login_required
@require_POST
def set_status(request, pk):
    item = get_object_or_404(Cinematography, pk=pk)
    status = request.POST.get('status', '')
    valid = dict(WatchlistEntry.STATUS_CHOICES)
    if status and status not in valid:
        return _respond(request, item, 'Unknown status.', {}, messages.ERROR, 400)
    if not status:
        WatchlistEntry.objects.filter(user=request.user, item=item).delete()
        return _respond(request, item, f'“{item.title}” removed from your lists.', {'status': ''})
    WatchlistEntry.objects.update_or_create(user=request.user, item=item, defaults={'status': status})
    return _respond(request, item, f'“{item.title}” marked as {valid[status]}.',
                    {'status': status, 'label': valid[status]})


@login_required
@require_POST
def rate_title(request, pk):
    item = get_object_or_404(Cinematography, pk=pk)
    raw = request.POST.get('score', '')
    if raw in ('', '0', 'delete'):
        Rating.objects.filter(user=request.user, item=item).delete()
        message, score = 'Your rating was removed.', None
    else:
        try:
            score = int(raw)
        except ValueError:
            score = 0
        if not 1 <= score <= 10:
            return _respond(request, item, 'Rating must be between 1 and 10.', {}, messages.ERROR, 400)
        Rating.objects.update_or_create(user=request.user, item=item, defaults={'score': score})
        message = f'You rated “{item.title}” {score}/10.'
    stats = item.ratings.aggregate(avg=Avg('score'), count=Count('id'))
    return _respond(request, item, message, {'score': score, 'avg': stats['avg'], 'count': stats['count']})


@login_required
@require_POST
def review_title(request, pk):
    item = get_object_or_404(Cinematography, pk=pk)
    existing = Review.objects.filter(user=request.user, item=item).first()
    if request.POST.get('action') == 'delete':
        if existing:
            existing.delete()
        return _respond(request, item, 'Your review was deleted.', {'deleted': True})
    form = ReviewForm(request.POST, instance=existing or Review(user=request.user, item=item))
    if not form.is_valid() or not form.cleaned_data['text'].strip():
        return _respond(request, item, 'Please write something before saving your review.', {},
                        messages.ERROR, 400)
    form.save()
    return _respond(request, item, 'Your review was updated.' if existing else 'Thanks for your review!', {})


# --------------------------------------------------------------------------- lists

@login_required
@require_POST
def list_create(request):
    form = UserListForm(request.POST, user=request.user)
    if form.is_valid():
        user_list = form.save(commit=False)
        user_list.user = request.user
        user_list.save()
        item_id = request.POST.get('item')
        if item_id and Cinematography.objects.filter(pk=item_id).exists():
            user_list.items.add(item_id)
        messages.success(request, f'List “{user_list.name}” created.')
    else:
        messages.error(request, ' '.join(e for errs in form.errors.values() for e in errs))
    return redirect(_safe_next(request, reverse('django_app:profile') + '?tab=lists'))


def list_detail(request, pk):
    user_list = get_object_or_404(UserList.objects.select_related('user'), pk=pk)
    if not user_list.is_public and user_list.user != request.user:
        raise Http404
    page_obj = Paginator(user_list.items.order_by('title'), PAGE_SIZE).get_page(request.GET.get('page'))
    statuses, ratings = _user_state(request.user, [i.id for i in page_obj])
    return render(request, 'django_app/list_detail.html', {
        'list': user_list, 'page_obj': page_obj, 'items': page_obj.object_list,
        'statuses': statuses, 'ratings': ratings, 'query_string': '',
        'page_range': page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1),
        'form': UserListForm(instance=user_list, user=request.user) if user_list.user == request.user else None,
    })


@login_required
@require_POST
def list_edit(request, pk):
    user_list = get_object_or_404(UserList, pk=pk, user=request.user)
    form = UserListForm(request.POST, instance=user_list, user=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, 'List updated.')
    else:
        messages.error(request, ' '.join(e for errs in form.errors.values() for e in errs))
    return redirect(user_list.get_absolute_url())


@login_required
@require_POST
def list_delete(request, pk):
    user_list = get_object_or_404(UserList, pk=pk, user=request.user)
    name = user_list.name
    user_list.delete()
    messages.success(request, f'List “{name}” deleted.')
    return redirect(reverse('django_app:profile') + '?tab=lists')


@login_required
@require_POST
def list_toggle_item(request, pk, item_pk):
    user_list = get_object_or_404(UserList, pk=pk, user=request.user)
    item = get_object_or_404(Cinematography, pk=item_pk)
    if user_list.items.filter(pk=item.pk).exists():
        user_list.items.remove(item)
        message, added = f'Removed from “{user_list.name}”.', False
    else:
        user_list.items.add(item)
        message, added = f'Added to “{user_list.name}”.', True
    user_list.save(update_fields=['updated_at'])
    return _respond(request, item, message, {'added': added})


# --------------------------------------------------------------------------- auth & profile

def register(request):
    if request.user.is_authenticated:
        return redirect('django_app:home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(username=form.cleaned_data['username'],
                                        email=form.cleaned_data['email'],
                                        password=form.cleaned_data['password'])
        login(request, user, backend='django_app.authentication.EmailOrUsernameModelBackend')
        messages.success(request, f'Welcome, {user.username}! Your account is ready.')
        return redirect('django_app:home')
    error = ' '.join(e for errs in form.errors.values() for e in errs) if form.errors else ''
    return render(request, 'django_app/register.html', {'form': form, 'error': error})


def login_(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request, reverse('django_app:home')))
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username', '').strip(),
                            password=request.POST.get('password', ''))
        if user is not None:
            login(request, user)
            if not request.POST.get('remember'):
                request.session.set_expiry(0)
            return redirect(_safe_next(request, reverse('django_app:home')))
        return render(request, 'django_app/login.html',
                      {'error1': 'Login or password is incorrect', 'next': request.POST.get('next', '')},
                      status=401)
    return render(request, 'django_app/login.html', {'next': request.GET.get('next', '')})


@require_POST
def logout_f(request):
    logout(request)
    return redirect('django_app:login')


PROFILE_TABS = [
    ('watching', 'Watching'), ('plan', 'Plan to Watch'), ('watched', 'Watched'),
    ('ratings', 'Ratings'), ('reviews', 'Reviews'), ('lists', 'Lists'),
]


def profile(request, username=None):
    if username is None:
        if not request.user.is_authenticated:
            return redirect(f"{reverse('django_app:login')}?next={request.path}")
        owner = request.user
    else:
        owner = get_object_or_404(User, username=username, is_active=True)
    is_owner = request.user == owner
    owner_profile, _ = Profile.objects.get_or_create(user=owner)

    tab = request.GET.get('tab', 'watching')
    if tab not in dict(PROFILE_TABS):
        tab = 'watching'

    status_counts = dict(owner.watchlist.values_list('status').annotate(n=Count('id')))
    rating_stats = owner.ratings.aggregate(avg=Avg('score'), count=Count('id'))
    lists_qs = owner.lists.annotate(n=Count('items')).order_by('-updated_at')
    if not is_owner:
        lists_qs = lists_qs.filter(is_public=True)
    counts = {
        'watching': status_counts.get('watching', 0), 'plan': status_counts.get('plan', 0),
        'watched': status_counts.get('watched', 0), 'ratings': rating_stats['count'],
        'reviews': owner.reviews.count(), 'lists': lists_qs.count(),
    }

    if tab in ('watching', 'plan', 'watched'):
        source = owner.watchlist.filter(status=tab).select_related('item')
    elif tab == 'ratings':
        source = owner.ratings.select_related('item')
    elif tab == 'reviews':
        source = owner.reviews.select_related('item')
    else:
        source = lists_qs.prefetch_related(Prefetch('items', queryset=Cinematography.objects.order_by('-popularity')))
    page_obj = Paginator(source, PAGE_SIZE).get_page(request.GET.get('page'))
    item_ids = [getattr(e, 'item_id', None) for e in page_obj if hasattr(e, 'item_id')]
    statuses, ratings = _user_state(request.user, item_ids)

    favourite_genres = (Genre.objects.filter(titles__ratings__user=owner, titles__ratings__score__gte=7)
                        .annotate(n=Count('id')).order_by('-n')[:5])

    return render(request, 'django_app/profile.html', {
        'owner': owner, 'owner_profile': owner_profile, 'is_owner': is_owner,
        'tabs': [(k, label, counts[k]) for k, label in PROFILE_TABS], 'tab': tab,
        'page_obj': page_obj, 'query_string': f'tab={tab}',
        'page_range': page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1),
        'rating_stats': rating_stats, 'statuses': statuses, 'ratings': ratings,
        'favourite_genres': favourite_genres,
        'list_form': UserListForm(user=request.user) if is_owner else None,
        'status_choices': WatchlistEntry.STATUS_CHOICES,
    })


@login_required
def profile_update(request):
    user_profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
        if pform.is_valid():
            pform.save()
            messages.success(request, 'Profile updated.')
            return redirect('django_app:profile')
    else:
        pform = ProfileUpdateForm(instance=user_profile)
    return render(request, 'django_app/profile_update.html', {'pform': pform})


def about(request):
    return render(request, 'django_app/about.html', {
        'total_titles': Cinematography.objects.count(),
        'total_users': User.objects.count(),
        'total_ratings': Rating.objects.count(),
        'gemini_enabled': bool(settings.GEMINI_API_KEY),
        'tmdb_enabled': tmdb.is_configured(),
    })
