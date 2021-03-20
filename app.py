import asyncpg
import aiohttp
from datetime import date, datetime, timedelta
from quart import Quart, request, abort, redirect, jsonify, send_file
from utils.time import Time
from models import Examination, Patient
import config
import io
import json
import random

app = Quart(__name__)


@app.before_serving
async def setup_pool():
    app.pool = await asyncpg.create_pool(config.postgresql)
    app.session = aiohttp.ClientSession()


@app.after_serving
async def close_pool():
    await app.pool.close()
    await app.session.close()


@app.route('/')
def hello_world():
    return '<samp>VJ#9010 on Discord. Feature requests rarely accepted.</samp>'


@app.route('/gestation')
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
    edd = (dt.dt.date() + timedelta(days=7 * 41)).strftime('%d %b %Y')

    gest_age = divmod((date.today() - dt.dt.date() - timedelta(days=7)).days, 7)
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
    patient = await app.pool.fetchrow(query, data['name'], data['age'], data['sex'], data['occupation'], datetime.strptime(data['doa'], '%d %b %Y').date(), next_of_kin['id'])
    return redirect('/patients/{}'.format(patient['id']))


@app.route('/patients/<int:id>/<int:exam_id>', methods=['GET', 'PATCH'])
async def get_examination(id, exam_id):
    """GET deetails of a specific examination for a patient.
    
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


if __name__ == '__main__':
    app.run(port=5445)
