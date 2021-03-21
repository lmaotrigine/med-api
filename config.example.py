postgresql = 'postgresql://user:password@host:port/database'
api_key = 'long_random_string'  # for protected endpoints.
cat_cdn = ''  # local CDN server for catposts. Check out https://thecatapi.com for a public API instead if you like.
# The follwoing is weird structure but it's what I could patch quickly after the massive data loss due to the OVH fire.
dog_db = ''  # a web app endpoint that spits out a random filename of a dog photo/video.
# you can use a database here, but I don't want to add a table to the existing database just for dogposts
dog_cdn = ''  # the actual CDN server that serves the dog media.
# Instead of these two separate things, you can use a public API.
