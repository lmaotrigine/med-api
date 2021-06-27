import config
import datetime

class LastFMClient:
    def __init__(self, session):
        self.session = session
        self.cached = {'track': 'server starting', 'artist': 'beep boop', 'current': True}
        self.cached_date = None
    async def update_cache(self):
        self.cached_date = datetime.datetime.utcnow()
        params={
            'method': 'user.getrecenttracks',
            'user': config.fm_username,
            'api_key': config.fm_api_key,
            'format': 'json',
            'limit': 1,
        }
        async with self.session.get('https://ws.audioscrobbler.com/2.0/', params=params) as resp:
            if resp.status != 200:
                return
            js = await resp.json()

        self.cached['track'] = js['recenttracks']['track'][0]['name']
        self.cached['artist'] = js['recenttracks']['track'][0]['artist']['#text']
        try:
            attrib = js['recenttracks']['track'][0].get('@attr')
        except IndexError:
            self.cached['current'] = False
        else:
            if attrib is not None:
                self.cached['current'] = attrib['nowplaying'] == 'true'
            else:
                self.cached['current'] = False

    async def get_info(self):
        if self.cached_date is None or datetime.datetime.utcnow() - self.cached_date > datetime.timedelta(seconds=60):
            await self.update_cache()
        return self.cached

