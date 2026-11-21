import datetime
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from django_app import ai
from django_app.models import (Cinematography, Genre, Rating, Review, UserList, WatchlistEntry,
                               profile)


def make_title(title, category='movie', genres=(), **kw):
    defaults = dict(description=kw.pop('description', 'A story'),
                    release_date=kw.pop('release_date', datetime.date(2020, 1, 1)))
    item = Cinematography.objects.create(title=title, category=category, **defaults, **kw)
    if genres:
        item.genres.add(*Genre.objects.filter(slug__in=genres))
    return item


class BaseTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('alice', 'alice@example.com', 'Str0ng-pass-123')

    def login(self):
        self.client.login(username='alice', password='Str0ng-pass-123')


class AuthTests(BaseTest):
    def test_profile_created_by_signal(self):
        self.assertTrue(profile.objects.filter(user=self.user).exists())

    def test_register_logs_in(self):
        resp = self.client.post(reverse('django_app:register'), {
            'username': 'bob', 'email': 'bob@example.com', 'password': 'An0ther-pass-456'})
        self.assertRedirects(resp, reverse('django_app:home'))
        self.assertTrue(User.objects.filter(username='bob').exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='bob').pk)

    def test_register_rejects_duplicates_and_weak_password(self):
        resp = self.client.post(reverse('django_app:register'), {
            'username': 'alice', 'email': 'ALICE@example.com', 'password': '123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already')
        self.assertEqual(User.objects.count(), 1)

    def test_login_with_username_or_email_and_safe_next(self):
        resp = self.client.post(reverse('django_app:login'),
                                {'username': 'alice@example.com', 'password': 'Str0ng-pass-123',
                                 'next': '/browse/'})
        self.assertRedirects(resp, '/browse/')
        self.client.logout()
        resp = self.client.post(reverse('django_app:login'),
                                {'username': 'alice', 'password': 'Str0ng-pass-123',
                                 'next': 'https://evil.example.com/'})
        self.assertRedirects(resp, reverse('django_app:home'))

    def test_bad_login(self):
        resp = self.client.post(reverse('django_app:login'), {'username': 'alice', 'password': 'nope'})
        self.assertEqual(resp.status_code, 401)
        self.assertContains(resp, 'incorrect', status_code=401)

    def test_logout_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(reverse('django_app:logout')).status_code, 405)
        self.client.post(reverse('django_app:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_protected_pages_redirect(self):
        for name in ('profile', 'profile_update'):
            resp = self.client.get(reverse(f'django_app:{name}'))
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse('django_app:login'), resp['Location'])

    def test_user_without_profile_gets_one(self):
        profile.objects.filter(user=self.user).delete()
        self.login()
        self.assertEqual(self.client.get(reverse('django_app:profile')).status_code, 200)
        self.assertTrue(profile.objects.filter(user=self.user).exists())


class FilteringTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.a = make_title('Space Wars', 'movie', ['action', 'sci-fi'], tmdb_rating=8.1, popularity=90,
                            release_date=datetime.date(2015, 5, 1))
        self.b = make_title('Funny Family', 'cartoons', ['comedy', 'family'], tmdb_rating=6.0, popularity=50)
        self.c = make_title('Аватар', 'movie', ['action', 'adventure'], tmdb_rating=7.0, popularity=70,
                            release_date=datetime.date(2009, 12, 1))
        self.d = make_title('Ninja Tales', 'anime', ['action', 'fantasy'], tmdb_rating=7.5, popularity=60)
        self.e = make_title('Office Life', 'series', ['comedy'], tmdb_rating=8.8, popularity=80)

    def titles(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return [i.title for i in resp.context['items']]

    def test_all_categories_work(self):
        for slug, expected in (('movies', {'Space Wars', 'Аватар'}), ('series', {'Office Life'}),
                               ('cartoons', {'Funny Family'}), ('anime', {'Ninja Tales'})):
            self.assertEqual(set(self.titles(reverse('django_app:catalog_category', args=[slug]))), expected)

    def test_unknown_category_404(self):
        self.assertEqual(self.client.get('/browse/unknown/').status_code, 404)

    def test_multi_genre_any_and_all(self):
        url = reverse('django_app:catalog')
        self.assertEqual(set(self.titles(f'{url}?genres=sci-fi&genres=comedy')),
                         {'Space Wars', 'Funny Family', 'Office Life'})
        self.assertEqual(self.titles(f'{url}?genres=action&genres=sci-fi&genre_mode=all'), ['Space Wars'])
        # comma separated form and no duplicates when a title matches several genres
        self.assertEqual(len(self.titles(f'{url}?genres=action,sci-fi')), 3)

    def test_combined_filters_and_sorting(self):
        url = reverse('django_app:catalog')
        self.assertEqual(self.titles(f'{url}?category=movie&genres=action&min_rating=7.5'), ['Space Wars'])
        self.assertEqual(self.titles(f'{url}?year_from=2010&year_to=2016'), ['Space Wars'])
        self.assertEqual(self.titles(f'{url}?sort=rating')[0], 'Office Life')
        self.assertEqual(self.titles(f'{url}?sort=title')[0], 'Funny Family')
        self.assertEqual(self.titles(f'{url}?sort=newest')[-1], 'Аватар')

    def test_search_by_title_including_cyrillic(self):
        url = reverse('django_app:catalog')
        self.assertEqual(self.titles(f'{url}?q=space'), ['Space Wars'])
        self.assertEqual(self.titles(f'{url}?q=аватар'), ['Аватар'])

    def test_invalid_params_are_ignored(self):
        self.assertEqual(len(self.titles(reverse('django_app:catalog') + '?year_from=abc&sort=bogus&page=x')), 5)

    def test_sort_by_community_rating(self):
        Rating.objects.create(user=self.user, item=self.b, score=10)
        self.assertEqual(self.titles(reverse('django_app:catalog') + '?sort=user_rating')[0], 'Funny Family')

    def test_legacy_home_params_redirect(self):
        resp = self.client.get('/home?cinematography=anime&genre=action')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('category=anime', resp['Location'])
        self.assertIn('genres=action', resp['Location'])
        self.assertRedirects(self.client.get('/all_movies/'), '/browse/movies/')


class PaginationTests(BaseTest):
    def test_pagination_keeps_filters(self):
        for i in range(30):
            make_title(f'Movie {i:02}', 'movie', ['drama'], popularity=i)
        url = reverse('django_app:catalog') + '?genres=drama&sort=title'
        first = self.client.get(url)
        self.assertEqual(len(first.context['items']), 24)
        self.assertContains(first, 'genres=drama&amp;sort=title&page=2')
        second = self.client.get(url + '&page=2')
        self.assertEqual([i.title for i in second.context['items']], [f'Movie {i}' for i in range(24, 30)])
        last = self.client.get(url + '&page=999')
        self.assertEqual(last.context['page_obj'].number, 2)


@override_settings(GEMINI_API_KEY='')
class AIFallbackTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.space = make_title('Stars', 'movie', ['sci-fi'], description='Robots explore deep space')
        self.comedy = make_title('Laughs', 'movie', ['comedy', 'family'], description='A cheerful story')
        self.horror = make_title('Night', 'movie', ['horror'], description='A haunted house')

    def test_query_analysis_understands_mood(self):
        p = ai.analyse_query('космос и роботы', 'хочу что-то весёлое')
        self.assertIn('sci-fi', p.genres)
        self.assertIn('comedy', p.genres)

    def test_fallback_without_key(self):
        resp = self.client.get(reverse('django_app:catalog') + '?mood=funny')
        rec = resp.context['recommendation']
        self.assertEqual(rec.source, ai.SOURCE_FALLBACK)
        self.assertEqual(resp.context['items'][0], self.comedy)
        self.assertContains(resp, 'not configured')

    def test_whole_database_is_considered(self):
        for i in range(400):
            make_title(f'Filler {i}', 'movie', ['drama'], popularity=1000)
        target = make_title('Deep Space Nine', 'series', ['sci-fi'], description='space station')
        ids = ai.rank_locally(Cinematography.objects.all(), 'space station', '')
        self.assertIn(target.id, ids[:3])

    @override_settings(GEMINI_API_KEY='test-key')
    def test_gemini_error_falls_back_and_cools_down(self):
        with mock.patch('django_app.ai.requests.post', side_effect=requests.ConnectionError('down')) as post:
            rec = ai.recommend(Cinematography.objects.all(), 'space', 'scary')
            self.assertEqual(rec.source, ai.SOURCE_FALLBACK)
            self.assertTrue(rec.ids)
            ai.recommend(Cinematography.objects.all(), 'other', 'query')
            self.assertEqual(post.call_count, 1)  # cool-down skips Gemini

    @override_settings(GEMINI_API_KEY='test-key')
    def test_gemini_ids_are_validated_and_cached(self):
        fake = mock.Mock(status_code=200)
        fake.raise_for_status.return_value = None
        fake.json.return_value = {'choices': [{'message': {'content':
            f'{{"ids": [{self.horror.id}, 99999, "x", {self.space.id}, {self.horror.id}]}}'}}]}
        with mock.patch('django_app.ai.requests.post', return_value=fake) as post:
            rec = ai.recommend(Cinematography.objects.all(), 'thrills', 'scary')
            again = ai.recommend(Cinematography.objects.all(), 'thrills', 'scary')
        self.assertEqual(rec.source, ai.SOURCE_AI)
        self.assertEqual(rec.ids[:2], [self.horror.id, self.space.id])
        self.assertNotIn(99999, rec.ids)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(again.ids, rec.ids)

    def test_parse_ids_handles_markdown(self):
        self.assertEqual(ai.parse_ids('```json\n[3, 2, 7]\n```', {2, 3}, 10), [3, 2])
        self.assertEqual(ai.parse_ids('nonsense', {1}, 10), [])


class DetailTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.item = make_title('Dune', 'movie', ['sci-fi'], tmdb_rating=8.0, tmdb_vote_count=1000,
                               poster_path='/dune.jpg', tmdb_id=438631, media_type='movie')
        self.other = make_title('Arrival', 'movie', ['sci-fi'])

    @override_settings(TMDB_API_KEY='')
    def test_detail_page_shows_info_and_separate_ratings(self):
        Rating.objects.create(user=self.user, item=self.item, score=6)
        resp = self.client.get(self.item.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'TMDB rating')
        self.assertContains(resp, 'Community rating')
        self.assertContains(resp, 'https://image.tmdb.org/t/p/w500/dune.jpg')
        self.assertContains(resp, 'Sci-fi')
        self.assertEqual(resp.context['stats']['avg'], 6)
        self.assertIn(self.other, resp.context['similar'])

    def test_cards_link_to_detail(self):
        resp = self.client.get(reverse('django_app:catalog'))
        self.assertContains(resp, f'href="{self.item.get_absolute_url()}"')

    def test_missing_detail_404(self):
        self.assertEqual(self.client.get('/title/99999/').status_code, 404)

    @override_settings(TMDB_API_KEY='k')
    def test_tmdb_details_failure_is_graceful(self):
        with mock.patch('django_app.tmdb.requests.get', side_effect=requests.Timeout()):
            resp = self.client.get(self.item.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['details'])

    @override_settings(TMDB_API_KEY='k')
    def test_tmdb_details_rendered(self):
        fake = mock.Mock()
        fake.raise_for_status.return_value = None
        fake.json.return_value = {'runtime': 155, 'tagline': 'Fear is the mind-killer',
                                  'credits': {'cast': [{'name': 'Timothée', 'character': 'Paul'}],
                                              'crew': [{'job': 'Director', 'name': 'Denis'}]},
                                  'videos': {'results': [{'site': 'YouTube', 'type': 'Trailer', 'key': 'abc'}]}}
        with mock.patch('django_app.tmdb.requests.get', return_value=fake):
            resp = self.client.get(self.item.get_absolute_url())
        self.assertContains(resp, '155 min')
        self.assertContains(resp, 'Fear is the mind-killer')
        self.assertContains(resp, 'youtube.com/watch?v=abc')
        self.assertContains(resp, 'Denis')


class RatingReviewWatchlistTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.item = make_title('Alien', 'movie', ['horror', 'sci-fi'])
        self.login()

    def test_anonymous_cannot_rate(self):
        self.client.logout()
        resp = self.client.post(reverse('django_app:rate_title', args=[self.item.id]), {'score': 5})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Rating.objects.exists())

    def test_rate_update_remove(self):
        url = reverse('django_app:rate_title', args=[self.item.id])
        self.client.post(url, {'score': 7})
        self.client.post(url, {'score': 9})
        self.assertEqual(Rating.objects.get().score, 9)
        self.assertEqual(self.client.post(url, {'score': 11}).status_code, 302)
        self.assertEqual(Rating.objects.get().score, 9)
        resp = self.client.post(url, {'score': 3}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.json()['score'], 3)
        self.assertEqual(self.client.post(url, {'score': 'abc'}, HTTP_X_REQUESTED_WITH='fetch').status_code, 400)
        self.client.post(url, {'score': 'delete'})
        self.assertFalse(Rating.objects.exists())

    def test_rating_constraints(self):
        Rating.objects.create(user=self.user, item=self.item, score=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Rating.objects.create(user=self.user, item=self.item, score=6)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Rating.objects.filter(user=self.user).update(score=0)

    def test_review_create_edit_delete(self):
        url = reverse('django_app:review_title', args=[self.item.id])
        self.client.post(url, {'text': 'Great!'})
        self.client.post(url, {'text': 'Even better', 'contains_spoilers': 'on'})
        review = Review.objects.get()
        self.assertEqual(review.text, 'Even better')
        self.assertTrue(review.contains_spoilers)
        self.assertContains(self.client.get(self.item.get_absolute_url()), 'Even better')
        self.client.post(url, {'text': '   '})
        self.assertEqual(Review.objects.get().text, 'Even better')
        self.client.post(url, {'action': 'delete'})
        self.assertFalse(Review.objects.exists())

    def test_users_cannot_touch_others_reviews(self):
        other = User.objects.create_user('eve', 'eve@example.com', 'Str0ng-pass-999')
        Review.objects.create(user=other, item=self.item, text='Mine')
        self.client.post(reverse('django_app:review_title', args=[self.item.id]), {'action': 'delete'})
        self.assertTrue(Review.objects.filter(user=other).exists())

    def test_watchlist_status_flow(self):
        url = reverse('django_app:set_status', args=[self.item.id])
        self.client.post(url, {'status': 'plan'})
        self.client.post(url, {'status': 'watching'})
        self.assertEqual(WatchlistEntry.objects.get().status, 'watching')
        resp = self.client.post(url, {'status': 'watched'}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.json()['status'], 'watched')
        self.assertEqual(WatchlistEntry.objects.count(), 1)
        self.assertEqual(self.client.post(url, {'status': 'bogus'}, HTTP_X_REQUESTED_WITH='fetch').status_code, 400)
        self.client.post(url, {'status': ''})
        self.assertFalse(WatchlistEntry.objects.exists())
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_status_redirects_to_safe_next(self):
        url = reverse('django_app:set_status', args=[self.item.id])
        resp = self.client.post(url, {'status': 'plan', 'next': '/browse/?page=2'})
        self.assertRedirects(resp, '/browse/?page=2', fetch_redirect_response=False)
        resp = self.client.post(url, {'status': 'plan', 'next': '//evil.com'})
        self.assertEqual(resp['Location'], self.item.get_absolute_url())


class ProfileAndListTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.item = make_title('Up', 'cartoons', ['family'])
        self.login()

    def test_profile_tabs(self):
        WatchlistEntry.objects.create(user=self.user, item=self.item, status='watched')
        Rating.objects.create(user=self.user, item=self.item, score=8)
        Review.objects.create(user=self.user, item=self.item, text='Sweet')
        for tab, text in (('watched', 'Up'), ('ratings', '8/10'), ('reviews', 'Sweet'), ('lists', 'No lists')):
            resp = self.client.get(reverse('django_app:profile') + f'?tab={tab}')
            self.assertContains(resp, text)
        self.assertEqual(self.client.get(reverse('django_app:profile') + '?tab=bad').status_code, 200)

    def test_public_profile(self):
        self.client.logout()
        resp = self.client.get(reverse('django_app:user_profile', args=['alice']))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Edit profile')

    def test_profile_update(self):
        resp = self.client.post(reverse('django_app:profile_update'), {'city': 'Almaty', 'description': 'Hi'})
        self.assertRedirects(resp, reverse('django_app:profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, 'Almaty')

    def test_lists_crud(self):
        self.client.post(reverse('django_app:list_create'),
                         {'name': 'Faves', 'is_public': 'on', 'item': self.item.id})
        user_list = UserList.objects.get()
        self.assertIn(self.item, user_list.items.all())
        self.client.post(reverse('django_app:list_create'), {'name': 'faves'})
        self.assertEqual(UserList.objects.count(), 1)  # duplicate names rejected
        self.client.post(reverse('django_app:list_toggle_item', args=[user_list.id, self.item.id]))
        self.assertFalse(user_list.items.exists())
        self.client.post(reverse('django_app:list_edit', args=[user_list.id]), {'name': 'Private', 'description': ''})
        user_list.refresh_from_db()
        self.assertFalse(user_list.is_public)
        self.client.logout()
        self.assertEqual(self.client.get(user_list.get_absolute_url()).status_code, 404)
        self.login()
        self.assertEqual(self.client.get(user_list.get_absolute_url()).status_code, 200)
        self.client.post(reverse('django_app:list_delete', args=[user_list.id]))
        self.assertFalse(UserList.objects.exists())

    def test_cannot_modify_other_users_list(self):
        other = User.objects.create_user('eve', 'eve@example.com', 'Str0ng-pass-999')
        theirs = UserList.objects.create(user=other, name='Theirs')
        resp = self.client.post(reverse('django_app:list_delete', args=[theirs.id]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(UserList.objects.filter(pk=theirs.pk).exists())


class PagesTests(BaseTest):
    def test_public_pages_render(self):
        make_title('Something', 'movie', ['drama'], tmdb_vote_count=100, tmdb_rating=7)
        for name in ('index', 'home', 'catalog', 'about', 'login', 'register'):
            self.assertEqual(self.client.get(reverse(f'django_app:{name}')).status_code, 200, name)

    def test_home_empty_catalog(self):
        self.assertContains(self.client.get('/'), 'fetch_movies')


class FetchCommandTests(TestCase):
    @override_settings(TMDB_API_KEY='k')
    def test_import_classifies_and_links_legacy_rows(self):
        from django.core.management import call_command
        legacy = Cinematography.objects.create(title='Spirited Away', category='movie', description='old',
                                               release_date=datetime.date(2001, 7, 20))
        page = {'total_pages': 1, 'results': [
            {'id': 129, 'title': 'Spirited Away', 'genre_ids': [16, 14], 'original_language': 'ja',
             'overview': '', 'release_date': '2001-07-20', 'vote_average': 8.5, 'vote_count': 15000,
             'popularity': 90, 'poster_path': '/sa.jpg'},
            {'id': 1399, 'name': 'Game of Thrones', 'genre_ids': [10765, 18], 'original_language': 'en',
             'overview': 'Dragons', 'first_air_date': '2011-04-17', 'vote_average': 8.4},
        ]}
        fake = mock.Mock()
        fake.raise_for_status.return_value = None
        fake.json.return_value = page
        with mock.patch('django_app.tmdb.requests.get', return_value=fake):
            call_command('fetch_movies', pages=1, categories=['movie'], stdout=mock.Mock())
            call_command('fetch_movies', pages=1, categories=['movie'], stdout=mock.Mock())
        legacy.refresh_from_db()
        self.assertEqual(legacy.tmdb_id, 129)
        self.assertEqual(legacy.category, 'anime')
        self.assertEqual(legacy.description, 'old')  # not wiped
        self.assertEqual(set(legacy.genres.values_list('slug', flat=True)), {'animation', 'fantasy'})
        got = Cinematography.objects.get(tmdb_id=1399)
        self.assertEqual(set(got.genres.values_list('slug', flat=True)), {'sci-fi', 'fantasy', 'drama'})
        self.assertEqual(Cinematography.objects.count(), 2)  # second run did not duplicate
