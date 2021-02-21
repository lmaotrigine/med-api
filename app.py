import asyncpg
from datetime import date, datetime, timedelta
from quart import Quart, request, abort, redirect
from utils.time import Time
from models import Examination, Patient
import config

app = Quart(__name__)


@app.before_serving
async def setup_pool():
    app.pool = await asyncpg.create_pool(config.postgresql)


@app.after_serving
async def close_pool():
    await app.pool.close()


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
        return 'bad request', 400
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
    if request.headers.get('Authorization') != config.api_key:
        if request.args.get('key') != config.api_key:
            return 'Not Authorised', 401
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
    if request.headers.get('Authorization') != config.api_key:
        if request.args.get('key') != config.api_key:
            return 'Not authorised', 401
    if request.method == 'GET':
        data = []
        query = 'SELECT * FROM patients ORDER BY id;'
        patients = await app.pool.fetch(query)
        for record in patients:
            patient = Patient.build_from_record(record)
            data.append(dict(name=patient.name, age=patient.age, sex=patient.sex, occupation=patient.occupation))
        return data
    data = await request.json
    nok = data['next_of_kin']
    nok = (nok['name'], nok['age'], nok['sex'], nok['occupation'])
    query = 'INSERT INTO relations (name, age, sex, occupation) VALUES ($1, $2, $3, $4) RETURNING *;'
    next_of_kin = await app.pool.fetchrow(query, *nok)
    query = "INSERT INTO patients (name, age, sex, occupation, date_of_admission, next_of_kin_id) VALUES " \
            "($1, $2, $3, $4, $5, $6) RETURNING *;"
    patient = await app.pool.fetchrow(query, data['name'], data['age'], data['sex'], data['occupation'], datetime.strptime(data['doa'], '%d %b %Y').date(),
                                      next_of_kin['id'])
    return redirect('/patients/{}'.format(patient['id']))


if __name__ == '__main__':
    app.run(port=5445)
