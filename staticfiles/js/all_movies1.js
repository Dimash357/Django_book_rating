document.addEventListener('DOMContentLoaded', function() {
    const apiKey = '412e1fa867ae38b44964ee52762a6463'; // Вставь твой ключ API здесь
    let currentPage = 1;
    const pageNumberElement = document.getElementById('page-number');

    function fetchMovies(page) {
        const apiUrl = `https://api.themoviedb.org/3/movie/popular?api_key=${apiKey}&language=ru-RU&page=${page}`;
        fetch(apiUrl)
            .then(response => response.json())
            .then(data => {
                const moviesList = document.getElementById('movies-list');
                moviesList.innerHTML = ''; // Clear the list before adding new movies
                data.results.forEach(movie => {
                    const movieItem = document.createElement('li');

                    const moviePoster = document.createElement('img');
                    moviePoster.src = `https://image.tmdb.org/t/p/w500${movie.poster_path}`;
                    moviePoster.alt = movie.title;

                    const movieInfo = document.createElement('div');
                    movieInfo.textContent = movie.title;

                    movieItem.appendChild(moviePoster);
                    movieItem.appendChild(movieInfo);
                    moviesList.appendChild(movieItem);
                });
                pageNumberElement.textContent = page;
                document.getElementById('prev-page').disabled = page === 1;
                document.getElementById('next-page').disabled = !data.total_pages || page === data.total_pages;
            })
            .catch(error => console.error('Error fetching movies:', error));
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

    // Fetch the first page of movies
    fetchMovies(currentPage);
});