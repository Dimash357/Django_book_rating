document.addEventListener('DOMContentLoaded', function() {
    const apiKey = '412e1fa867ae38b44964ee52762a6463';
    let currentPage = 1;
    const pageNumberElement = document.getElementById('page-number');

    function fetchMovies(page) {
        const cachedMovies = localStorage.getItem(`movies-page-${page}`);
        if (cachedMovies) {
            renderMovies(JSON.parse(cachedMovies), page);
        } else {
            const apiUrl = `https://api.themoviedb.org/3/movie/popular?api_key=${apiKey}&language=ru-RU&page=${page}`;
            fetch(apiUrl)
                .then(response => response.json())
                .then(data => {
                    localStorage.setItem(`movies-page-${page}`, JSON.stringify(data.results));
                    renderMovies(data.results, page);
                })
                .catch(error => console.error('Error fetching movies:', error));
        }
    }

    function renderMovies(movies, page) {
        const moviesList = document.getElementById('movies-list');
        moviesList.innerHTML = '';
        movies.forEach(movie => {
            const movieItem = document.createElement('li');

            const moviePoster = document.createElement('img');
            moviePoster.src = 'placeholder.jpg'; // Placeholder image
            moviePoster.dataset.src = `https://image.tmdb.org/t/p/w500${movie.poster_path}`;
            moviePoster.alt = movie.title;
            moviePoster.classList.add('lazy');

            const movieInfo = document.createElement('div');
            movieInfo.textContent = movie.title;

            movieItem.appendChild(moviePoster);
            movieItem.appendChild(movieInfo);
            moviesList.appendChild(movieItem);
        });
        pageNumberElement.textContent = page;
        document.getElementById('prev-page').disabled = page === 1;
        document.getElementById('next-page').disabled = !movies.length;

        lazyLoadImages();
    }

    function lazyLoadImages() {
        const lazyImages = [].slice.call(document.querySelectorAll('img.lazy'));
        if ('IntersectionObserver' in window) {
            let lazyImageObserver = new IntersectionObserver(function(entries, observer) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        let lazyImage = entry.target;
                        lazyImage.src = lazyImage.dataset.src;
                        lazyImage.classList.remove('lazy');
                        lazyImageObserver.unobserve(lazyImage);
                    }
                });
            });

            lazyImages.forEach(function(lazyImage) {
                lazyImageObserver.observe(lazyImage);
            });
        } else {
            let lazyLoadThrottleTimeout;
            function lazyLoad() {
                if (lazyLoadThrottleTimeout) {
                    clearTimeout(lazyLoadThrottleTimeout);
                }

                lazyLoadThrottleTimeout = setTimeout(function() {
                    let scrollTop = window.pageYOffset;
                    lazyImages.forEach(function(img) {
                        if (img.offsetTop < (window.innerHeight + scrollTop)) {
                            img.src = img.dataset.src;
                            img.classList.remove('lazy');
                        }
                    });
                    if (lazyImages.length == 0) {
                        document.removeEventListener('scroll', lazyLoad);
                        window.removeEventListener('resize', lazyLoad);
                        window.removeEventListener('orientationChange', lazyLoad);
                    }
                }, 20);
            }

            document.addEventListener('scroll', lazyLoad);
            window.addEventListener('resize', lazyLoad);
            window.addEventListener('orientationChange', lazyLoad);
        }
    }

    document.getElementById('prev-page').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchMovies(currentPage);
        }
    });

    document.getElementById('next-page').addEventListener('click', () => {
        currentPage++;
        fetchMovies(currentPage);
    });

    fetchMovies(currentPage);
});
