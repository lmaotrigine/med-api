from datetime import date, timedelta
from quart import Quart, request, abort
from utils.time import Time

app = Quart(__name__)


@app.route('/')
def hello_world():
    return 'VJ#9010 on Discord. Feature requests rarely accepted.'


@app.route('/gestation')
async def get_gestation_age():
    if dt := request.args.get('lmp') is None:
        abort(400)
    try:
        dt = Time(dt)
    except ValueError:
        return 'bad request', 400
    if dt._past is False:
        return 'This date is in the future.', 400
    w, d = divmod((dt.dt.date() + timedelta(days=7 * 41)).days, 7)

    gest_age = divmod((date.today() - dt.dt.date() + timedelta(days=7)).days, 7)
    return {'edd': f'{w}.{d}', 'gestation_age': f'{gest_age[0]}.{gest_age[1]}'}


if __name__ == '__main__':
    app.run()
