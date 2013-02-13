from Dashboard import connect_db
from contextlib import closing
import sqlite3, csv, re, datetime

with closing(connect_db()) as db:
    with open('schema.sql') as f:
        db.cursor().executescript(f.read())
    db.commit()

    with open('tcnzdsldata.csv', 'rb') as f:
        data = csv.reader(f)

        for row in data:
            try:
                if re.match('^\d{10}$', row[0]) and re.match('^[A-Z]{2,3}[-|_|/]([A-Z]{1,3}-)?DSLAM-\d{0,2}$', row[6]):

                    cur = db.execute('select id, name from dslams where name==?', [row[6]])
                    dslam = cur.fetchone()

                    if dslam is None:
                        db.execute('insert into dslams (name) values (?)', [row[6]])
                        db.commit()
                        cur = db.execute('select id, name from dslams where name==?', [row[6]])
                        dslam = cur.fetchone()
                
                    cur = db.execute('select id, dslam_id from dslusers where asid==?', [row[0]])
                    dsluser = cur.fetchone()

                    if dsluser is None:
                        db.execute('insert into dslusers (asid, dslam_id) values (?,?)', [row[0], dslam[0]])
                    elif dsluser[1] != dslam[1]:
                        db.execute('update dslusers set dslam_id=(?) where id==(?)', [dslam[0], dsluser[0]])

                    db.commit()
            except IndexError as e:
                print("Bad data somewhere. Continuing.") 

    with open('internaldsldata.csv', 'rb') as f:
        data = csv.reader(f)

        for row in data:
            try:
                if re.match('^\d{10}$', row[0]):

                    cur = db.execute('select id, asid from dslusers where asid==?', [row[1]])
                    user = cur.fetchone()

                    if user is not None:
                        cur = db.execute('update dslusers set account_name=(?), phone_number=(?), user_name=(?) where id==?',
                                [str(row[1]), str(row[2]), str(row[3]), user[0]])
                        db.commit()
            except IndexError as e:
                print("Bad data somewhere. Continuing.") 
            except sqlite3.ProgrammingError as e:
                pdb.set_trace()

