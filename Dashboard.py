from flask import Flask, render_template, g, request, flash, redirect, url_for
from contextlib import closing
import datetime, re, sqlite3

#App setup
app = Flask(__name__)
app.config.from_pyfile('settings.cfg')

#Sqlite helpers
def connect_db():
    return sqlite3.connect(app.config['DATABASE'], detect_types = sqlite3.PARSE_DECLTYPES)

#Init
@app.before_request
def before_request():
	g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()

#Routes
@app.route('/')
def main_interface():
    cur = g.db.execute('select id, provider, num_affected, end_time, flagged from outages where start_time<? and (end_time is null or end_time>? ) and hidden==0 order by start_time desc',
            [datetime.datetime.now(), datetime.datetime.now()])
    outages = [dict(id=row[0], provider=row[1],
        num_affected=row[2], end_time=row[3], flagged=row[4]) for row in cur.fetchall()]

    for outage in outages:
        cur = g.db.execute('select provider_ref_id from outage_texts where rowid==?', [outage['id']])
        outage['provider_ref'] = cur.fetchone()
        cur = g.db.execute('select dslusers_id from outages_dslusers_rel where outages_id==?', [outage['id']])

        dsluser_ids = '('
        for row in cur.fetchall():
            dsluser_ids += str(row[0]) + ', '
        dsluser_ids = dsluser_ids.rstrip().rstrip(',')
        dsluser_ids += ')'

        cur = g.db.execute('select id, asid, account_name, phone_number, user_name from dslusers where id IN ' + dsluser_ids)
        outage['users'] = [dict(id=row[0], asid=row[1], account_name=row[2], phone_number=row[3], user_name=row[4]) for row in cur.fetchall()]
        
        cur = g.db.execute('select count(*) from outages_dslusers_rel where outages_id==?', [outage['id']])
        outage['our_affected'] = cur.fetchone()[0]

    return render_template('base.html', queues=queues, notes=notes,
            outages=outages)
			
#Outages stuff
@app.route('/outages/<int:outage_id>')
def outage_detail(outage_id):
    cur = g.db.execute('select id, provider, num_affected, start_time, end_time, checked, flagged, text_id issues from outages where id==?',
            [outage_id])
    outage = cur.fetchone()
    cur = g.db.execute('select provider_ref_id, equipment_list, full_text from outage_texts where rowid==?', [outage[7]])
    outage_texts = cur.fetchone()

    checked = None

    if outage[5] == 0:
        checked = False
    elif outage[5] == 1:
        checked = True

    flagged = None

    if outage[6] == 0:
        flagged = False
    elif outage[6] == 1:
        flagged = True
    
    issues = None

    if outage[7] == 0:
        issues = False
    elif outage[7] == 1:
        issues = True

    outage = dict(id=outage[0], provider=outage[1], provider_reference=outage_texts[0],
        num_affected=outage[2], start_time=outage[3], end_time=outage[4],
        full_text=outage_texts[2], checked=checked, flagged=flagged,
        issues=issues, equipment_list=outage_texts[1])

    cur = g.db.execute('select dslusers_id from outages_dslusers_rel where outages_id == ?', [outage_id])

    dsluser_ids = '('
    for row in cur.fetchall():
        dsluser_ids += str(row[0]) + ', '
    dsluser_ids = dsluser_ids.rstrip().rstrip(',')
    dsluser_ids += ')'
    cur = g.db.execute('select id, asid, account_name, phone_number, user_name from dslusers where id IN ' + dsluser_ids)
    dslusers = [dict(id=row[0], asid=row[1], account_name=row[2], phone_number=row[3], user_name=row[4]) for row in cur.fetchall()]

    return render_template('outage_detail.html', outage=outage, dslusers=dslusers, providers=app.config['PROVIDERS'])

@app.route('/outages/new')
def outage_new():
    return render_template('outage_new.html', providers=app.config['PROVIDERS'])

@app.route('/outages/create', methods=['POST'])
def outage_create():
    checked = False
    if request.form.get('checked') is not None:
        checked = True

    flagged = False 
    if request.form.get('flagged') is not None:
        flagged = True

    start_datetime = None
    if request.form.get('start_datetime') is not None:
        try:
            start_datetime = datetime.datetime.strptime(request.form.get('start_datetime'),
                '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            flash('Start Date/Time formatted incorrectly')
            return redirect(url_for('outage_new'))

    end_datetime = None
    if (request.form.get('end_datetime') is not None) and ('None' not in request.form.get('end_datetime')):
        try:
            end_datetime = datetime.datetime.strptime(request.form.get('end_datetime'),
                '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            flash('End Date/Time formatted incorrectly')
            return redirect(url_for('outage_new'))

    return redirect(url_for('outage_detail', outage_id=outage_id))

@app.route('/outages/<int:outage_id>/edit', methods=['POST']) 
def outage_edit(outage_id):

    checked = False
    if request.form.get('checked') is not None:
        checked = True

    flagged = False 
    if request.form.get('flagged') is not None:
        flagged = True

    start_datetime = None
    if request.form.get('start_datetime') is not None:
        try:
            start_datetime = datetime.datetime.strptime(request.form.get('start_datetime'),
                '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            flash('Start Date/Time formatted incorrectly')
            return redirect(url_for('outage_detail', outage_id=outage_id))

    end_datetime = None
    if (request.form.get('end_datetime') is not None) and ('None' not in request.form.get('end_datetime')):
        try:
            end_datetime = datetime.datetime.strptime(request.form.get('end_datetime'),
                '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            flash('End Date/Time formatted incorrectly')
            return redirect(url_for('outage_detail', outage_id=outage_id))

    g.db.execute('update outages set num_affected=(?), start_time=(?), end_time=(?), checked=(?), flagged=(?) where id == ?',
        [int(request.form.get('num_affected')),
            start_datetime, end_datetime, checked, flagged, outage_id])
    g.db.execute('update outage_texts set equipment_list=(?) where rowid == (select text_id from outages where id == ?)', [request.form.get('equipment'), outage_id])
    g.db.commit()

    users = list()

    for line in request.form.get('equipment').split('\n'):
        cur = g.db.execute('select id, name from dslams where name==?', [line])
        dslam = cur.fetchone()
        if dslam is not None:
            cur = g.db.execute('select id, asid from dslusers where dslam_id==?', [dslam[0]])
            users.append(cur.fetchall())

    g.db.execute('delete from outages_dslusers_rel where outages_id == ?', [outage_id])
    g.db.commit()

    for db_block in users:
        for user in db_block:
            if user is not None:
                g.db.execute('insert into outages_dslusers_rel (outages_id, dslusers_id) values (?,?)',
                        [outage_id, user[0]])
                g.db.commit()
    flash('Outage Updated')
    return redirect(url_for('outage_detail', outage_id=outage_id))

@app.route('/outages/', defaults={'page_number':1})
@app.route('/outages/list/', defaults={'page_number':1})
@app.route('/outages/list/<int:page_number>')
def outage_list(page_number):
    cur = g.db.execute('select id, provider, text_id, num_affected, start_time, end_time, checked, flagged, issues from outages order by start_time desc limit 15 offset ?', [(page_number - 1) * 15])
    outages = [dict(id=row[0], provider=row[1], text_id=row[2],
        num_affected=row[3], start_time=row[4], end_time=row[5],
        checked=row[6], flagged=row[7], issues=row[8]) for row in cur.fetchall()]
    for outage in outages:
        cur = g.db.execute('select count(*) from outages_dslusers_rel where outages_id==?', [outage['id']])
        outage['our_affected'] = cur.fetchone()[0]
        cur = g.db.execute('select provider_ref_id from outage_texts where rowid==?', [outage['text_id']])
        outage['provider_reference'] = cur.fetchone()[0]
    return render_template('outage_list.html', outages=outages,
            page_number=page_number)

@app.route('/outages/search/', methods=['POST'])
def outage_serach_form():
    return redirect(url_for('outage_search_url', search_string=request.form.get('search_string')))

@app.route('/outages/search/<search_string>/', defaults={'page_number':1})
@app.route('/outages/search/<search_string>/<int:page_number>')
def outage_search_url(search_string, page_number):
    cur = g.db.execute('select rowid, provider_ref_id from outage_texts where full_text match ?', [search_string])
    outages = [dict(text_id=row[0], provider_reference=row[1]) for row in cur.fetchall()]
    outages = outages[(page_number - 1) * 15: page_number * 15]
    for outage in outages:
        cur = g.db.execute('select id, provider, num_affected, start_time, end_time, checked, flagged, issues from outages where text_id == (?)', [outage['text_id']])
        data = cur.fetchone()
        outage['id'] = data[0]
        outage['provider'] = data[1]
        outage['num_affected'] = data[2]
        outage['start_time'] = data[3]
        outage['end_time'] = data[4]
        outage['checked'] = data[5]
        outage['flagged'] = data[6]
        outage['issues'] = data[7]

    for outage in outages:
        cur = g.db.execute('select count(*) from outages_dslusers_rel where outages_id==?', [outage['id']])
        outage['our_affected'] = cur.fetchone()[0]

    return render_template('outage_search.html', outages=outages, page_number=page_number, search_string=search_string)

@app.route('/settings')
def settings():
    #Controls for the parsers etc. Be warned. This will probably be dangerous as all hell
    with open('settings.cfg', 'r') as f:
        return render_template('settings.html', settings = f.read())

@app.route('/settings/edit', methods=['POST'])
def settings_edit():
    with open('settings.cfg', 'w') as f:
        f.write(request.form.get('settings'))
    return redirect(url_for('settings'))

@app.route('/settings/reload')
def settings_reload():
    #TODO: an are you sure thing, run through test parse or something
    app.config.from_pyfile('settings.cfg')
    flash('Config reloaded. Better yet, if you\'re seeing this, it probably worked')
    return redirect(url_for('settings'))

#Makes runnable
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
