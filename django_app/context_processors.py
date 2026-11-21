from .models import Cinematography

CATEGORY_NAV = [
    ('movies', 'movie', 'Movies'),
    ('series', 'series', 'Series'),
    ('cartoons', 'cartoons', 'Cartoons'),
    ('anime', 'anime', 'Anime'),
]


def site_context(request):
    return {'category_nav': CATEGORY_NAV, 'category_labels': dict(Cinematography.CATEGORY_CHOICES)}
