from bs4 import BeautifulSoup
from Dashboard import connect_db
from flask import Config
import sys, re, datetime, sqlite3, os, imaplib, email, pdb, smtplib, logging

def FromEmails():

    #Config, init variables
    config = Config(os.getcwd())
    config.from_pyfile('settings.cfg')

    logger = logging.getLogger('ICONZ.HelpdeskDashboard.OutageParse')
    logger.addHandler(config['HANDLER'])

    def GetBody(msg):
        if msg.is_multipart():
            return(msg.get_payload(0)).get_payload(decode=True)
        else:
            return(msg.get_payload(decode=True))



    def Passthrough(msg_list):
        try:
            smtp_conn = smtplib.SMTP(config['OUTAGES_SMTP_SERVER'],
                    config['OUTAGES_SMTP_PORT'])

            for msg in msg_list:
                smtp_conn.sendmail(config['OUTAGES_SMTP_FROM_ADDR'],
                    config['OUTAGES_SMTP_TO_ADDR'], msg.as_string())

            logger.info('Succesfully passed through ' + str(len(msg_list)) + ' messages')
        except Exception as e:
            logger.error('Faliure to passthrough all messages.', exc_info = True)
            


    def DBInsert(data):
        #Could tidy this up so it's done as a batch operation. Probably unecessary
        conn = connect_db()
        cur = conn.cursor()

        try:
            cur.execute('select rowid from outage_texts where provider_ref_id match(?)',
                    [data['reference']])

            db_outage = cur.fetchone()
            db_outage_id = None
            db_outage_text_id = None

            if db_outage == None:
                cur.execute('insert into outage_texts (provider_ref_id, equipment_list, full_text) values (?,?,?)',
                    [unicode(data['reference']), unicode(data['equipment']), unicode(data['full_text'])])
                db_outage_text_id = cur.lastrowid
                cur.execute('insert into outages (provider, num_affected, start_time, end_time, issues, text_id) values (?,?,?,?,?,?)',
                    [data['provider'], data['num_affected'], data['start_datetime'], data['end_datetime'], data['issues'], db_outage_text_id])

                db_outage_id = cur.lastrowid
                conn.commit()

                logger.debug('Created new outage with id ' + str(db_outage_id))

            else:
                cur.execute('update outage_texts set equipment_list=(?), full_text=(?) where rowid==?',
                        [unicode(data['equipment']), unicode(data['full_text']), db_outage[0]])
                db_outage_text_id = db_outage[0]
                cur.execute('select id from outages where text_id==?', [db_outage_text_id])
                db_outage_id = cur.fetchone()[0]
                cur.execute('update outages set num_affected=(?), start_time=(?), end_time=(?), issues=(?) where id==?',
                        [data['num_affected'], data['start_datetime'], data['end_datetime'], data['issues'], db_outage_id])

                conn.commit()

                logger.debug('Updated outage with id ' + str(db_outage_id))


            users = list()

            for line in data['equipment'].split('\n'):
                cur.execute('select id, name from dslams where name==?', [line])
                dslam = cur.fetchone()
                if dslam is not None:
                    cur.execute('select id, asid from dslusers where dslam_id==?', [dslam[0]])
                    users.append(cur.fetchall())

            for db_block in users:
                for user in db_block:
                    if user is not None:
                        cur.execute('select * from outages_dslusers_rel where (outages_id==?) and (dslusers_id==?)', [db_outage_id, user[0]])
                        if cur.fetchone() is None:
                            cur.execute('insert into outages_dslusers_rel (outages_id, dslusers_id) values (?,?)',
                                    [db_outage_id, user[0]])
                            conn.commit()
        #Clears connection so that program can continue in case of exception
        except sqlite3.IntegrityError as e:
            conn.close()
            conn = connect_db()
            raise(e)

                        
    def ChorusHTMLFat(data):

        def FindContent(fieldname, soup, one = True):
            if one:
                out = [string for string in soup.find(
                    "td", text=re.compile(fieldname), style=re.compile('(;color:|; COLOR: )rgb\(0,72,97\);')
                    ).parent.find(
                    "td", style=re.compile('(;color:|; COLOR: )rgb\(0,0,0\);')
                    ).stripped_strings]
                if len(out) < 1: return None
                else: return out[0]
            else:
                return [string for string in soup.find(
                    "td", text=re.compile(fieldname), style=re.compile('(;color:|; COLOR: )rgb\(0,72,97\);')
                    ).parent.find(
                    "td", style=re.compile('(;color:|; COLOR: )rgb\(0,0,0\);')
                    ).stripped_strings]
        
        soup = BeautifulSoup(data)

        results = dict({'provider' : 'Chorus', 'reference' : FindContent('Ticket Number:', soup), 'issues' : False})

        try:
            start_date = FindContent('Date:', soup)
            start_time = FindContent('Start Time:', soup)
            if start_time is not None:
                if start_time.endswith('(amended)'):
                    start_time = start_time[0:6]
            else:
                results['issues'] = True
                start_time = '00:00'

            results['start_datetime'] = datetime.datetime.strptime(start_date + ' ' +
                start_time, '%d/%m/%Y %H:%M')

        except (AttributeError, ValueError):
            results['issues'] = True
            results['start_datetime'] = None

        try:
            end_date = FindContent('Resolution Date:', soup)
            end_time = FindContent('Resolution Time:', soup)

            if end_date is None:
                if end_time is None:
                    results['end_datetime'] = None
                else:
                    results['end_datetime'] = datetime.datetime.combine(start_datetime.date,
                            datetime.time.strptime(end_time, '%H:%M'))
            else:
                results['end_datetime'] = datetime.datetime.strptime(end_date + ' ' +
                    end_time, '%d/%m/%Y %H:%M')
        except (AttributeError, ValueError):
            results['end_datetime'] = None

        try:
            results['num_affected'] = int(re.search(('(\d+)'), FindContent('Customer Impact:',
                soup)).group(1))
        except AttributeError:
            results['issues'] = True
            results['num_affected'] = 0

        #Might be useful later if I can get ASID -> DSLAM mappings
        equipment = FindContent('Equipment List:', soup, False)
        results['equipment'] = ''

        for string in equipment:
            if re.match('[A-Z]{2,3}[-|_|/]([A-Z]{1,3}-)?DSLAM-\d{0,2}', string):
                results['equipment'] += string + '\n'
            else:
                results['issues'] = True

        results['full_text'] = ''

        for string in soup.stripped_strings:
            if re.match('^VF \w{1,3}$', string):
                string = ''
            results['full_text'] = results['full_text'] + string + '\n'

        return results



    def ChorusPlainText(f):

        results = dict({'provider' : 'Chorus', 
            'reference' : re.search(('SED Ref.+:.+(\d{6})'), f).group(1),
            'issues' : False})

        start_date = re.search(('DATE.+:.+(\d{2}/\d{2}/\d{2})'), f)
        start_time = re.search(('NZ Standard Time.+:.+(\d{2}:\d{2}:\d{2}.(AM|PM))'), f)

        results['start_datetime'] = datetime.datetime.strptime(start_date.group(1) + ' ' +
                start_time.group(1), '%d/%m/%y %I:%M:%S %p')

        duration = re.search(('DURATION \(HR:MIN:SEC\).+:.+(\d{3}):(\d{2}):(\d{2})'), f)

        results['end_datetime'] = results['start_datetime'] + datetime.timedelta(hours = int(duration.group(1)), 
                minutes = int(duration.group(2)), seconds = int(duration.group(3))) 

        try:
            results['num_affected'] = int(re.search('Up to (\d+) DSL customers', f).group(1))
        except AttributeError:
            results['issues'] = True
            results['num_affected'] = 0
            logger.warning('ChorusPlainText could not extract num_affected')
        equipment = re.findall(('([A-Z]{2,3}[-|_|/]([A-Z]{1,3}-)?DSLAM-\d{0,2})'), f)

        results['equipment'] = ''

        for regex_groups in equipment:
            results['equipment'] += regex_groups[0] + '\n'

        if 'DSLAM' not in results['equipment']:
            results['issues'] = True
            logger.warning('ChorusPlainText could not extract equipment_list')

        results['full_text'] = str(f)

        if results['issues'] == False:
            logger.debug('ChorusPlainText parsed message without issue')

        return results



    def ChorusHTMLSkinny(outage):

        soup = BeautifulSoup(outage)

        results = dict({'provider' : 'Chorus', 'issues' : False})

        text = ''
        
        #Mandated by shitty HTML
        stringgen = soup.stripped_strings
        for string in stringgen:
            if ('Field' not in string) and ('FIELD' not in string):
                if 'Ticket Number:' in string:
                    stringgen.next()
                    results['reference'] = stringgen.next()
                    text += results['reference'] + '\n' 
                elif 'Location:' in string:
                    stringgen.next()
                    results['location'] = stringgen.next()
                    text += results['location'] + '\n'
                elif 'Start Date:' in string:
                    stringgen.next()
                    results['start_datetime'] = stringgen.next()
                    text += results['start_datetime'] + '\n'
                elif 'Start Time:' in string:
                    stringgen.next()
                    temp = stringgen.next()
                    results['start_datetime'] = results['start_datetime'] + ' ' + temp
                    text += temp + '\n'
                elif 'Resolution Date:' in string:
                    stringgen.next()
                    results['end_datetime'] = stringgen.next()
                    text += results['end_datetime'] + '\n'
                elif 'Resolution Time:' in string:
                    stringgen.next()
                    temp = stringgen.next()
                    results['end_datetime'] += ' ' + temp
                    text += temp + '\n'
                elif 'Customer Impact:' in string:
                    stringgen.next()
                    temp = stringgen.next()
                    try:    
                        results['num_affected'] = int(re.search('Up to (\d+) DSL customers', temp).group(1))
                    except AttributeError:
                        results['issues'] = True
                        results['num_affected'] = 0
                        logger.warning('ChorusHTMLSkinny could not extract num_affected')
                    text += temp + '\n'
                elif 'Equipment List:' in string:
                    results['equipment'] = ''
                    stringgen.next()
                    temp = stringgen.next()
                    while 'Additional Information:' not in temp:
                        results['equipment'] += temp
                        text += temp + '\n'
                        temp = stringgen.next()
                elif 'Cable Pair & Range:' in string:
                    results['equipment'] = ''
                    stringgen.next()
                    temp = stringgen.next()
                    while 'Additional Information:' not in temp:
                        results['equipment'] += temp
                        text += temp + '\n'
                        temp = stringgen.next()
                else:
                    text += string + '\n'

        if (results['start_datetime'] is not None) and (len(results['start_datetime']) == 16):
            try:
                results['start_datetime'] = datetime.datetime.strptime(results['start_datetime'], '%d/%m/%Y %H:%M')
            except ValueError:
                try:
                    results['start_datetime'] = datetime.datetime.strptime(results['start_datetime'], '%H:%M %d/%m/%Y')
                except ValueError:
                    results['issues'] = True
                    results['start_datetime'] = None
                    logger.warning('ChorusHTMLSkinny could not extract start_datetime')
        elif results['start_datetime'] is not None:
            results['issues'] = True
            results['start_datetime'] = None
            logger.warning('ChorusHTMLSkinny could not extract start_datetime')
        else:
            results['issues'] = True
            logger.error('Fallthrough condition in ChorusHTMLSkinny when parsing start_datetime')

        if (results['end_datetime'] is not None) and (len(results['end_datetime']) == 16):
            try:
                results['end_datetime'] = datetime.datetime.strptime(results['end_datetime'], '%d/%m/%Y %H:%M')
            except ValueError:
                try:
                    results['end_datetime'] = datetime.datetime.strptime(results['end_datetime'], '%H:%M %d/%m/%Y')
                except ValueError:
                    results['issues'] = True
                    results['end_datetime'] = None
                    logger.warning('ChorusHTMLSkinny could not extract end_datetime')

        else:
            results['end_datetime'] = None
            logger.warning('ChorusHTMLSkinny could not extract end_datetime')

        results['full_text'] = text

        if results['issues'] == False:
            logger.debug('ChorusHTMLSkinny parsed message without issue')

        return results

    #Actual script begins here.

    passthrough_list = list()

    #IMAP login
    imap = imaplib.IMAP4(config['OUTAGES_POP_SERVER'])
    imap.login(config['OUTAGES_POP_USER'], config['OUTAGES_POP_PASS'])
    imap.select('INBOX')

    ids = None

    if config['DEBUG'] is True:
        ids = imap.search(None, '(SUBJECT "")')[1][0].split() 
    else:   
        ids = imap.search(None, '(UNSEEN)')[1][0].split()

    if len(ids) > 0:
        logger.info('Collected ' + str(len(ids)) + 'messages from inbox')
    
    #Fetch messages
    for id in ids:
        typ, msg_data = imap.fetch(id, '(RFC822)')
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_string(response_part[1])
                data = None
                
                #Choose parser
                if (msg.has_key('from')) and (msg.has_key('subject')):
                    if (config['CHORUS_PLAIN_TEXT_FROM_ADDRS_RE'].search(msg['from'])) and (config['CHORUS_PLAIN_TEXT_RE'].match(msg['subject'])):
                        logger.debug('Message ' + msg['subject'] + 'passed to ChorusPlainText parser')
                        data = ChorusPlainText(GetBody(msg))

                    elif (config['CHORUS_HTML_FAT_FROM_ADDRS_RE'].search(msg['from'])) and (config['CHORUS_HTML_FAT_RE'].match(msg['subject'])):
                        logger.debug('Message ' + msg['subject'] + 'passed to ChorusHTMLFat parser')
                        data = ChorusHTMLFat(GetBody(msg))

                    elif (config['CHORUS_HTML_SKINNY_FROM_ADDRS_RE'].search(msg['from'])) and (config['CHORUS_HTML_SKINNY_RE'].match(msg['subject'])):
                        logger.debug('Message ' + msg['subject'] + 'passed to ChorusHTMLSkinny parser')
                        data = ChorusHTMLSkinny(GetBody(msg))

                    else:
                        passthrough_list.append(msg)
                        logger.warning('Could not select parser for message ' + msg['subject'])
                else:
                    logger.error('Unable to select parser due to missing headers')

                if data is not None:
                    try:
                        DBInsert(data)
                    except (sqlite3.IntegrityError, UnicodeDecodeError) as e:
                        logger.warning('Unable to insert data into db from message ' + msg['subject'], exc_info = True)
                        passthrough_list.append(msg)

    Passthrough(passthrough_list)

if __name__ == '__main__':
    FromEmails()
