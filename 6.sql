SELECT AVG(rating)
FROM ratings
WHERE movie_id IN
    (SELECT id
    FROM movies
    WHERE title = 2012);