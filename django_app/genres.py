"""Genre catalogue shared by the TMDB importer, filters and AI fallback."""

# slug -> display name
GENRES = {
    'action': 'Action',
    'adventure': 'Adventure',
    'animation': 'Animation',
    'comedy': 'Comedy',
    'crime': 'Crime',
    'documentary': 'Documentary',
    'drama': 'Drama',
    'family': 'Family',
    'fantasy': 'Fantasy',
    'history': 'History',
    'horror': 'Horror',
    'kids': 'Kids',
    'music': 'Music',
    'mystery': 'Mystery',
    'romance': 'Romance',
    'sci-fi': 'Sci-fi',
    'thriller': 'Thriller',
    'war': 'War',
    'western': 'Western',
    'reality': 'Reality',
    'tv-movie': 'TV Movie',
}

# TMDB genre id -> our slugs (movie and TV ids combined; TV uses composite genres)
TMDB_GENRE_MAP = {
    28: ['action'], 12: ['adventure'], 16: ['animation'], 35: ['comedy'],
    80: ['crime'], 99: ['documentary'], 18: ['drama'], 10751: ['family'],
    14: ['fantasy'], 36: ['history'], 27: ['horror'], 10402: ['music'],
    9648: ['mystery'], 10749: ['romance'], 878: ['sci-fi'], 10770: ['tv-movie'],
    53: ['thriller'], 10752: ['war'], 37: ['western'],
    10759: ['action', 'adventure'], 10762: ['kids'], 10764: ['reality'],
    10765: ['sci-fi', 'fantasy'], 10768: ['war'],
}

ANIMATION_TMDB_ID = 16

# Natural-language hints (English + Russian stems) used by the AI fallback
# and to give Gemini a smarter candidate pool.
MOOD_GENRE_HINTS = {
    ('happy', 'fun', 'funny', 'cheer', 'laugh', 'comedy', 'light', 'весел', 'смешн', 'радост',
     'комед', 'позитив', 'юмор', 'смех'): ['comedy', 'family', 'animation'],
    ('sad', 'cry', 'melanchol', 'emotional', 'touching', 'груст', 'печал', 'слез', 'трогат',
     'эмоци'): ['drama', 'romance'],
    ('scary', 'scared', 'fear', 'horror', 'creepy', 'spooky', 'страш', 'ужас', 'жутк', 'хоррор',
     'пуга'): ['horror', 'thriller'],
    ('love', 'romantic', 'romance', 'date', 'любов', 'романт', 'свидан'): ['romance', 'drama'],
    ('adventure', 'journey', 'explore', 'quest', 'приключ', 'путешеств'): ['adventure', 'action', 'fantasy'],
    ('tense', 'thrill', 'suspense', 'edge', 'напряж', 'триллер', 'саспенс'): ['thriller', 'mystery', 'crime'],
    ('relax', 'calm', 'cozy', 'chill', 'easy', 'tired', 'спокой', 'уют', 'расслаб', 'отдох',
     'устал', 'лёгк', 'легк'): ['comedy', 'family', 'animation', 'romance'],
    ('think', 'smart', 'philosoph', 'deep', 'mind', 'умн', 'философ', 'глубок', 'мысл', 'интеллект'):
        ['drama', 'sci-fi', 'mystery'],
    ('space', 'future', 'robot', 'alien', 'scifi', 'sci-fi', 'cyber', 'космос', 'будущ', 'робот',
     'инопланет', 'фантаст', 'кибер'): ['sci-fi'],
    ('magic', 'dragon', 'wizard', 'fairy', 'myth', 'маги', 'дракон', 'волшеб', 'сказ', 'фэнтез'): ['fantasy'],
    ('war', 'soldier', 'battle', 'войн', 'солдат', 'битв', 'сражен'): ['war', 'history', 'action'],
    ('crime', 'detective', 'mystery', 'murder', 'heist', 'mafia', 'детектив', 'преступ', 'убийств',
     'загад', 'мафи', 'ограблен'): ['crime', 'mystery', 'thriller'],
    ('action', 'fight', 'explosion', 'energetic', 'adrenaline', 'боевик', 'экшн', 'драк', 'энерг',
     'адренал'): ['action', 'adventure', 'thriller'],
    ('kid', 'child', 'family', 'дет', 'ребен', 'семь', 'семей'): ['family', 'animation', 'kids'],
    ('history', 'historical', 'истор'): ['history', 'war', 'drama'],
    ('music', 'musical', 'song', 'музык', 'песн'): ['music'],
    ('documentary', 'real story', 'true story', 'документ', 'реальн'): ['documentary', 'history'],
    ('western', 'cowboy', 'вестерн', 'ковбо'): ['western'],
}

CATEGORY_HINTS = {
    ('anime', 'аниме', 'manga', 'манга', 'japan', 'япон'): 'anime',
    ('cartoon', 'animated', 'pixar', 'disney', 'мульт'): 'cartoons',
    ('series', 'show', 'season', 'episode', 'сериал', 'сезон', 'серии'): 'series',
    ('movie', 'film', 'фильм', 'кино'): 'movie',
}


def genre_slugs_from_tmdb(ids):
    seen = []
    for gid in ids or []:
        for slug in TMDB_GENRE_MAP.get(gid, []):
            if slug not in seen:
                seen.append(slug)
    return seen
