import asyncpg
import aiohttp
from datetime import date, datetime, timedelta
from quart import Quart, render_template, request, Response, abort, redirect, jsonify, send_file
from utils.time import Time
from utils.tokens import TokenUtils
from utils.lastfm import LastFMClient
from models import Examination, Patient
import config
import functools
import io
import json
import random
import statistics

app = Quart(__name__)
token_handler = TokenUtils(app)


@app.before_serving
async def setup_pool():
    app.pool = await asyncpg.create_pool(config.postgresql)
    app.session = aiohttp.ClientSession()
    app.lastfm_client = LastFMClient(app.session)

@app.after_serving
async def close_pool():
    await app.pool.close()
    await app.session.close()


@app.after_request
async def add_header(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

def requires_auth(view):
    @functools.wraps(view)
    async def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token is None:
            abort(401)
        auth = await token_handler.validate_token(token)
        if auth is False:
            abort(401)
        user_id, app_id = auth
        if user_id is None or app_id is None:
            abort(401)
        return await view(*args, **kwargs)
    return wrapper


@app.route('/')
def hello_world():
    return '<samp>VJ#5945 on Discord. Feature requests rarely accepted.</samp>'


@app.route('/music')
async def jam_sessions():
    #return redirect('https://learnermanipal-my.sharepoint.com/:f:/g/personal/varun_j_learner_manipal_edu/EtNIRtF9dERLqjP4QiLYWOsBWHMXKDK1sluEXdKbx7TVMQ')
    return redirect('https://learnermanipal-my.sharepoint.com/:f:/g/personal/varun_j_learner_manipal_edu/EtNIRtF9dERLqjP4QiLYWOsBSH0VC0IOzm_6dPBEUcRviA?e=AzYwz6')

@app.route('/.well-known/keybase.txt')
@app.route('/keybase.txt')
async def keybase_validation():
    return await render_template('keybase.txt')


@app.route('/tokens')
async def token_page():
    return await render_template('tokens.html')


@app.route('/terms')
async def terms_of_service():
    return await render_template('terms.html')


@app.route('/gestation')
@requires_auth
async def get_gestation_age():
    """Return the Expected Delivery Date and the gestation age (in weeks.days format) given a date string corresponding
    to the last menstrual period.
    """
    if (dt := request.args.get('lmp')) is None:
        abort(400)
    try:
        dt = Time(dt)
    except ValueError:
        return '<samp>bad request</samp>', 400
    if dt._past is False:
        # pdt converts all dates to future when year isn't specified. We assume this was the case when the year is up
        # by one
        if dt.dt.date().year - date.today().year == 1:
            dt.dt = dt.dt.replace(year=date.today().year)
        else:
            return {'message': 'This date is in the future.', 'parsed_date': dt.dt.strftime('%d %b %Y')}, 400

    # This is not Naegle's but is in keeping with 40 weeks of gestation.
    edd = (dt.dt.date() + timedelta(days=7 * 41)).strftime('%d %b %Y')

    # Probably missed something here
    gest_age = divmod((date.today() - dt.dt.date()).days, 7)
    return {'lmp': dt.dt.date().strftime('%d %b %Y'), 'edd': edd, 'gestation_age': gest_age[0] + gest_age[1] * 0.1}


@app.route('/patients/<int:id>', methods=['GET', 'POST'])
async def get_patient_data(id):
    """GET a patient's details.
    
    POST examination details to append to their history.
    """
    if request.headers.get('Authorization') != config.api_key:
        if request.args.get('key') != config.api_key:
            return '<samp>Not Authorised</samp>', 401
    payload = {}
    data = await request.json
    record = await app.pool.fetchrow('SELECT * FROM patients WHERE id = $1;', id)
    patient = Patient.build_from_record(record)
    async with app.pool.acquire() as con:
        if request.method == 'GET':
            history = await patient.fetch_history(con=con)
        else:
            dt = data.get('date')
            if dt is not None:
                _date = datetime.strptime(dt, '%d %b %Y').date()
            else:
                _date = None
            history = await patient.add_exam(data['summary'], data['details'], _date, con=con)
        nok = await patient.get_next_of_kin(con=con)
    payload.update(**patient.__dict__)
    payload['history'] = [h.__dict__ for h in patient.history]
    payload['next_of_kin'] = nok.__dict__

    return payload


@app.route('/patients', methods=['POST', 'GET'])
async def post_patient_stats():
    """GET basic details of all patients
    
    POST details of a new patient. Redirects to the new patient's page.
    """
    if request.headers.get('Authorization') != config.api_key:
        if request.args.get('key') != config.api_key:
            return '<samp>Not authorised</samp>', 401
    if request.method == 'GET':
        data = []
        query = 'SELECT * FROM patients ORDER BY id;'
        patients = await app.pool.fetch(query)
        for record in patients:
            patient = Patient.build_from_record(record)
            data.append(dict(name=patient.name, age=patient.age, sex=patient.sex, occupation=patient.occupation))
        return jsonify(data)
    data = await request.json
    nok = data['next_of_kin']
    nok = (nok['name'], nok['age'], nok['sex'], nok['occupation'])
    query = 'INSERT INTO relations (name, age, sex, occupation) VALUES ($1, $2, $3, $4) RETURNING *;'
    next_of_kin = await app.pool.fetchrow(query, *nok)
    query = "INSERT INTO patients (name, age, sex, occupation, date_of_admission, next_of_kin_id) VALUES " \
            "($1, $2, $3, $4, $5, $6) RETURNING *;"
    patient = await app.pool.fetchrow(query, data['name'], data['age'], data['sex'], data['occupation'],
                                      datetime.strptime(data['doa'], '%d %b %Y').date(), next_of_kin['id'])
    return redirect('/patients/{}'.format(patient['id']))


@app.route('/patients/<int:id>/<int:exam_id>', methods=['GET', 'PATCH'])
async def get_examination(id, exam_id):
    """GET details of a specific examination for a patient.
    
    PATCH: Change the summary or details of an examination.
    """
    if request.headers.get('Authorization') != config.api_key:
        if request.args.get('key') != config.api_key:
            return '<samp>Not authorised</samp>', 401
    exam = await app.pool.fetchrow('SELECT * FROM examinations WHERE id = $1;')
    if request.method == 'GET':
        return dict(**exam)
    data = await request.json
    exam = Examination.build_from_record(exam)
    async with app.pool.acquire() as con:
        exam = await exam.amend(con, **data)
    return exam.__dict__


@app.route('/cat')
async def random_cat():
    """GET a random cat photo. Helps take the edge off. At least for me."""
    async with app.session.get(config.cat_cdn) as resp:
        if resp.status != 200:
            return '<samp>Could not find cat :(</samp>', 404
        js = await resp.json()
    async with app.session.get(js[0]['url']) as img:
        to_send = io.BytesIO(await img.read())
    return await send_file(to_send, 'image')


@app.route('/dog')
async def random_dog():
    """GET a random dog photo/video. This CDN is kinda wonky, you might want to redesign this when you fork."""
    async with app.session.get(config.dog_db) as resp:
        if resp.status != 200:
            return '<samp>Could not find dog :(</samp>', 404

        filename = await resp.text()
        url = f'{config.dog_cdn}/{filename}'
        async with app.session.get(url) as other:
            if other.status != 200:
                return '<samp>Could not download dog image/video :(</samp>', 404
            fp = io.BytesIO(await other.read())
        mimetype = 'video' if filename.endswith(('.mp4', '.webm')) else 'image'
        return await send_file(fp, mimetype)


@app.route('/antidepressant-or-tolkien')
async def drug_or_tolkien():
    return '<samp>Idea based on <a href="https://twitter.com/checarina/status/977387234226855936">@checarina</a>\'s' \
           'tweet.<br>Use the <a href="/antidepressant-or-tolkien/random">random</a> and ' \
           '<a href="/antidepressant-or-tolkien/all">all</a> endpoints as needed.</samp>'


@app.route('/antidepressant-or-tolkien/all')
async def drug_or_tolkien_all():
    if not hasattr(app, 'drug_or_tolkien_js'):
        with open('static/json/antidepressant_or_tolkien.json') as f:
            app.drug_or_tolkien_js = json.load(f)
    random.shuffle(app.drug_or_tolkien_js)
    return app.drug_or_tolkien_js


@app.route('/antidepressant-or-tolkien/random')
async def drug_or_tolkien_random():
    if not hasattr(app, 'drug_or_tolkien_js'):
        with open('static/json/antidepressant_or_tolkien.json') as f:
            app.drug_or_tolkien_js = json.load(f)
    return random.choice(app.drug_or_tolkien_js)


@app.route('/now-playing')
async def now_playing():
    resp = await app.lastfm_client.get_info()
    return resp


# central tendencies
"""
POST /mean; /median; /mode

Request body must be JSON encoded (or follow the JSON format)
Must be an array of numbers (integers or floating point numbers), or an array of JSON objects.

JSON objects in the array can have the following keys:
--------------------------------------------------------------------------
Key         | Type   | Required? | Description                           |
--------------------------------------------------------------------------
lower_limit | Number | No*       | The lower limit of the class interval |
upper_limit | Number | No*       | The upper limit of the class interval |
frequency   | Number | Yes       | The frequency of this class           |
mid         | Number | No*       | The mid point of this class interval  |
interval    | Number | No        | The height of this class interval     |
--------------------------------------------------------------------------

* lower_limit is required for /mode
* if mid is not specified, then both lower_limit and upper_limit need to be specified
* if both lower_limit and upper_limit are not specified, interval needs to be specified
"""


def send_error_message(e):
    if isinstance(e, Exception):
        message = f'{e.__class__.__name__}: {e}'
    else:
        message = str(e)
    print(message)
    return {'code': 400, 'message': message}, 400


def do_calc(data, what):
    if not data:
        return send_error_message('Data is empty.')
    if type(data) != list:
        return send_error_message('Data must be an array.')
    if not all(x in (int, float) for x in map(type, data)) and not all(x == dict for x in map(type, data)):
        return send_error_message('Data must be an array of JSON objects, or an array of floats.')
    if type(data[0]) == dict:
        arr = []
        interval = None
        for js in data:
            try:
                mid = js.get('mid') or (js['upper_limit'] + js['lower_limit']) / 2
                if interval is None:
                    interval = js.get('interval') or js['upper_limit'] - js['lower_limit']
                else:
                    if interval != js.get('interval') and interval != js['upper_limit'] - js['lower_limit']:
                        return send_error_message('Inconsistent class intervals.')
                arr += [mid] * js['frequency']
            except KeyError as e:
                return send_error_message(e)
    else:
        arr = [float(i) for i in data]
        interval = 1
    lookup = {
        'mean': statistics.mean,
        'median': lambda x: statistics.median_grouped(x, interval=interval),
        'mode': statistics.multimode
    }
    try:
        print(arr)
        print({what: lookup[what](arr)})
        return {what: lookup[what](arr)}
    except Exception as e:
        return send_error_message(e)


@app.route('/mode', methods=['POST'])
@requires_auth
async def do_mode():
    try:
        data = json.loads(await request.data)
    except Exception as e:
        return send_error_message(e)
    if not data:
        return send_error_message('Data is empty.')
    if type(data) != list:
        return send_error_message('Data must be an array.')
    if not all(x == dict for x in map(type, data)):
        return do_calc(data, 'mode')

    get_interval = lambda x: x.get('interval', (x['upper_limit'] - x['lower_limit']))
    try:
        interval = get_interval(data[0])
        if not all(x == interval for x in map(get_interval, data)):
            return send_error_message('Inconsistent class intervals.')
    except KeyError as e:
        return send_error_message(e)

    try:
        data = sorted(data, key=lambda x: x.get('mid', x['lower_limit']))
        modal_class = data.index(max(data, key=lambda x: x['frequency']))
        ll = data[modal_class]['lower_limit']
        one_less = modal_class - 1
        one_more = modal_class + 1
        print(data[modal_class]['frequency'], ll, data[one_more]['frequency'], data[one_less]['frequency'])
    except KeyError as e:
        return send_error_message(e)
    _mode = (((data[modal_class]['frequency'] - data[one_less]['frequency']) /
             (2 * data[modal_class]['frequency'] - data[one_less]['frequency'] - data[one_more]['frequency']))
             * interval) + ll
    print(_mode)
    return {'mode': _mode}


@app.route('/median', methods=['POST'])
@requires_auth
async def do_median():
    try:
        data = json.loads(await request.data)
    except Exception as e:
        return send_error_message(e)
    return do_calc(data, 'median')


@app.route('/mean', methods=['POST'])
@requires_auth
async def do_mean():
    try:
        data = json.loads(await request.data)
    except Exception as e:
        return send_error_message(e)
    return do_calc(data, 'mean')


if __name__ == '__main__':
    app.run(port=5445)
