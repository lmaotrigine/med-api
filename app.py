from datetime import date, timedelta
from quart import Quart, request, abort
from utils.time import Time

app = Quart(__name__)


@app.route('/')
def hello_world():
    return 'VJ#9010 on Discord. Feature requests rarely accepted.'


@app.route('/gestation')
async def get_gestation_age():
    if (dt := request.args.get('lmp')) is None:
        abort(400)
    try:
        dt = Time(dt)
    except ValueError:
        return 'bad request', 400
    if dt._past is False:
        if dt.dt.date().year - date.today().year == 1:
            print(date.today().year)
            dt.dt = dt.dt.replace(year=date.today().year)
            print(dt.dt)
        else:
            print(dt.dt)
            return {'message': 'This date is in the future.', 'parsed_date': dt.dt.strftime('%d %b %Y')}, 400
    print(dt.dt)
    edd = (dt.dt.date() + timedelta(days=7 * 41)).strftime('%d %b %Y')

    gest_age = divmod((date.today() - dt.dt.date() - timedelta(days=7)).days, 7)
    return {'edd': edd, 'gestation_age': gest_age[0] + gest_age[1] * 0.1}


if __name__ == '__main__':
    app.run()
