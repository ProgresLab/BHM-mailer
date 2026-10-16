"""No operational DB, SMTP socket or real clock waits. Run with unittest discovery."""
import os
os.environ['SMTP_ENABLED'] = 'false'

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from email import message_from_string
import hashlib
import hmac
import io
import json
from pathlib import Path
import smtplib
import sqlite3
import shutil
from uuid import uuid4
import threading
import time
import unittest
from unittest.mock import patch, PropertyMock
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from jinja2 import UndefinedError
from PIL import Image

from app import assets, db, mailer, worker
from app.email_renderer import render_campaign_single, EMAIL_LOGO_SRC
from app.rich_text import sanitize_html, html_to_text, safe_url
from app.selection import update_selection, selected_ids, selection_fingerprint
from app import main


def settings():
    return mailer.MailSettings('fake.invalid',465,'sender@example.test','test-password',
        'BHM Chemicals','sender@example.test','reply@example.test','sender@example.test',
        False,True,True,'https://unsubscribe.example.test/unsubscribe','test-signature',
        'admin@example.test',20,False)


def banner_bytes(size=(1200,400),fmt='PNG'):
    stream=io.BytesIO()
    Image.new('RGB',size,'#11263a').save(stream,fmt)
    return stream.getvalue()


class FakeClock:
    def __init__(self): self.now=1000000.
    def __call__(self): return self.now
    def advance(self,seconds): self.now+=seconds


class Case(unittest.TestCase):
    def setUp(self):
        self.test_root=Path(__file__).resolve().parents[1]/'output'/'test-runtime'/uuid4().hex
        root=self.test_root
        root.mkdir(parents=True)
        self.patches=[patch.object(db,'DB_PATH',root/'isolated.sqlite3'),patch.object(db,'DATA_DIR',root),
            patch.object(db,'UPLOADS_DIR',root/'uploads'),patch.object(assets,'ASSET_DIR',root/'assets'),
            patch.object(main,'UPLOADS_DIR',root/'uploads'),patch.object(mailer,'get_mail_settings',return_value=settings()),
            patch.object(main,'get_mail_settings',return_value=settings())]
        for p in self.patches:p.start()
        db.init_db()
        self.clock=FakeClock()
        self.starts=[]
        self.engine=worker.Engine(self.clock,self.fake_send,settings)
        self.client=TestClient(main.app) # Deliberately no lifespan/real worker.

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches):p.stop()
        assert self.test_root.is_relative_to(Path(__file__).resolve().parents[1]/'output'/'test-runtime')
        shutil.rmtree(self.test_root)

    def contacts(self,n=3):
        with db.get_connection() as conn:
            conn.executemany("""INSERT INTO contacts(email,company_name,country_group,language,status,unsubscribe_token,created_at,updated_at)
                VALUES(?,?,'PL','pl','active',?,?,?)""",
                [(f'qa{i:05}@example.test','Syntetyczny kontakt',f'token{i}',db.utc_now(),db.utc_now()) for i in range(n)])
            return [r[0] for r in conn.execute('SELECT id FROM contacts ORDER BY id')]

    def campaign(self,approved=True,banner=None):
        html='<p>Dzień dobry, <strong>oferta</strong> <em>BHM</em> <u>informacja</u>.</p><ul data-list="check"><li>Produkt testowy</li></ul><p><a href="https://bhm-chemicals.com/">Kontakt</a></p>'
        rendered=render_campaign_single('pl','Temat odbiorcy',None,body_html=html,headline='Nagłówek wiadomości',banner_asset=banner)
        with db.get_connection() as conn:
            return conn.execute('''INSERT INTO campaigns(name,subject,language,body,body_html,headline,html,text,banner_asset,status,created_at)
                VALUES('Nazwa wewnętrzna','Temat odbiorcy','pl',?,?,?,?,?,?,?,?)''',
                (html_to_text(html),html,'Nagłówek wiadomości',rendered['html'],rendered['text'],banner,'approved' if approved else 'draft',db.utc_now())).lastrowid

    def prepare(self,n=3,mode='smtp'):
        ids=self.contacts(n); cid=self.campaign()
        result=mailer.prepare_campaign_send(cid,ids,mode)
        self.assertTrue(result['started'])
        with db.get_connection() as conn:
            conn.execute('UPDATE campaign_execution SET started=?,updated=?',(self.clock(),self.clock()))
        return cid,ids

    def fake_send(self,*args,identity=None,**kwargs):
        self.starts.append(self.clock())
        # Proves another writer can commit DURING a network call.
        with db.get_connection() as conn:
            conn.execute("UPDATE contacts SET notes='test writer during SMTP' WHERE email=?",(args[1],))
        return mailer.SmtpSendResult('250','250 accepted (fake)',identity.message_id,
            identity.smtp_user,identity.header_from,identity.reply_to,identity.envelope_from,
            identity.envelope_to,identity.message_id)

    def row(self,query,params=()):
        with db.get_connection() as conn:
            return dict(conn.execute(query,params).fetchone())

    def test_new_campaign_requires_form_context_without_database_access(self):
        # The pre-modernization process omitted this context while Jinja loaded
        # the new template from disk: the original port-8000 HTTP 500.
        render = main.render_template

        def stale_context(request, name, context=None, status_code=200):
            context = dict(context or {})
            context.pop('form', None)
            return render(request, name, context, status_code)

        with patch.object(main, 'get_connection', side_effect=AssertionError('GET must not access SQLite')):
            with patch.object(main, 'render_template', side_effect=stale_context):
                with self.assertRaisesRegex(UndefinedError, "'form' is undefined"):
                    self.client.get('/campaigns/new')
            response = self.client.get('/campaigns/new')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'], {})
        self.assertIn('data-rich-editor', response.text)
        self.assertIn('role="toolbar"', response.text)
        self.assertEqual(self.row('SELECT COUNT(*) AS n FROM campaigns')['n'], 0)

    def test_rich_allowlist_and_text(self):
        value='<p style="font-family:Evil;font-size:18px;color:red" onclick="alert(1)">Zażółć <b>B</b> <i>I</i> <u>U</u> <a href="https://example.test/">link</a></p><script>alert(2)</script><img src=x onerror=alert(3)><a href="jav&#x61;script:alert(4)">X</a>'
        safe=sanitize_html(value)
        for bad in ('onclick','script','onerror','font-family','color:red','<img'):
            self.assertNotIn(bad,safe)
        self.assertIn('font-size:18px',safe)
        self.assertEqual(sanitize_html(safe),safe)
        self.assertIn('Zażółć B I U link (https://example.test/)',html_to_text(safe))
        self.assertNotIn('<',html_to_text(safe))

    def test_unsafe_url_variants(self):
        for url in ('javascript:alert(1)','data:text/html,x','//example.test','https://u:p@example.test/','https://example.test/\nX','file:///tmp/x'):
            self.assertFalse(safe_url(url),url)
        self.assertEqual(safe_url('https://bhm-chemicals.com/pl/produkty/'),'https://bhm-chemicals.com/pl/produkty/')

    def test_font_sizes_and_lists(self):
        for size in ('14px','16px','18px','22px','28px'):
            self.assertIn(size,sanitize_html(f'<span style="font-size:{size}">Test</span>'))
        self.assertNotIn('100px',sanitize_html('<p style="font-size:100px">Test</p>'))
        self.assertIn('font-size:22px',sanitize_html('<font size="5">Test</font>'))
        result=render_campaign_single('en','Subject',None,body_html='<ol><li>One</li></ol><ul data-list="check"><li>Two</li></ul>')
        self.assertIn('&#10003;',result['html']); self.assertIn('- One',result['text'])
        self.assertIn('If you no longer wish',result['text'])

    def test_draft_roundtrip_edit_and_lock(self):
        data=dict(name='Wewnętrzna',subject='Odbiorca',language='pl',headline='Nagłówek',body_html='<p><b>Żółć</b> <em>italics</em> <a href="https://example.test">link</a></p>')
        response=self.client.post('/campaigns/new',data=data,follow_redirects=False)
        self.assertEqual(response.status_code,303)
        row=self.row('SELECT * FROM campaigns')
        self.assertEqual(row['body_html'],sanitize_html(data['body_html']))
        self.assertNotEqual(row['name'],row['subject'])
        cid=row['id']
        self.assertIn('&lt;b&gt;Żółć',self.client.get(f'/campaigns/{cid}/edit').text)
        data['body_html']='<h2>Nowy</h2><p><u>tekst</u></p>'
        self.assertEqual(self.client.post(f'/campaigns/{cid}/edit',data=data,follow_redirects=False).status_code,303)
        self.client.post(f'/campaigns/{cid}/approve')
        before=self.row('SELECT * FROM campaigns')
        self.assertEqual(self.client.post(f'/campaigns/{cid}/edit',data=data).status_code,400)
        self.assertEqual(before,self.row('SELECT * FROM campaigns'))

    def test_draft_invalid_fields_and_cta(self):
        data=dict(name='Name',subject='Subject',language='de',headline='Headline',body_html='<p>Body</p>')
        self.assertEqual(self.client.post('/campaigns/new',data=data).status_code,400)
        data.update(language='en',cta_label='Click',cta_url='javascript:evil')
        self.assertEqual(self.client.post('/campaigns/new',data=data).status_code,400)

    def test_banner_validation_and_private_preview(self):
        key=assets.store_banner(banner_bytes())
        self.assertTrue(assets.asset_path(key).exists())
        with Image.open(assets.asset_path(key)) as image:self.assertEqual(image.size,(1200,400))
        cid=self.campaign(banner=key)
        self.assertEqual(self.client.get('/campaign-assets/'+key).status_code,200)
        response=self.client.get(f'/campaigns/{cid}/preview')
        self.assertEqual(response.status_code,200)
        self.assertIn('/campaign-assets/'+key,response.text)
        self.assertNotIn('cid:bhm-banner',response.text)
        self.assertEqual(self.client.get('/uploads/campaign_assets/'+key).status_code,404)
        for bad in (b'<svg/>',b'<html/>',b'x'*(assets.MAX_UPLOAD+1),banner_bytes((1200,600)),banner_bytes((300,100)),banner_bytes(fmt='GIF')):
            with self.assertRaises(ValueError):assets.store_banner(bad)
        with self.assertRaises(ValueError):assets.asset_path('../../.env')

    def test_banner_upload_route_and_mime(self):
        data=dict(name='Banner',subject='Subject',language='en',headline='Headline',body_html='<p>Body</p>')
        response=self.client.post('/campaigns/new',data=data,files={'banner':('wrong.txt',banner_bytes(),'text/plain')},follow_redirects=False)
        self.assertEqual(response.status_code,303)
        row=self.row('SELECT * FROM campaigns')
        captured=[]
        class FakeSMTP:
            def __init__(self,*a,**kw):pass
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def ehlo(self):pass
            def login(self,*a):pass
            def sendmail(self,**kw):captured.append(kw);return {}
        with patch.object(mailer.smtplib,'SMTP_SSL',FakeSMTP):
            mailer.send_one_email(settings(),'one@example.test','Subject',row['text'],row['html'],banner_asset=row['banner_asset'])
        mime=message_from_string(captured[0]['msg'])
        cids=[p.get('Content-ID') for p in mime.walk() if p.get('Content-ID')]
        self.assertIn('<bhm-chemicals-logo>',cids)
        self.assertIn('<'+assets.banner_cid(row['banner_asset'])+'>',cids)
        self.assertEqual(captured[0]['to_addrs'],['one@example.test'])
        self.assertNotIn('Bcc',mime);self.assertNotIn('Cc',mime)
        self.assertIn('href="https://bhm-chemicals.com/"',row['html'])
        self.assertNotIn('uploads/',row['html'])

    def test_legacy_campaign_and_logo_fallback(self):
        result=render_campaign_single('pl','Stara kampania','Pierwszy akapit\n\nDrugi: <test>')
        self.assertIn('&lt;test&gt;',result['html']);self.assertIn(EMAIL_LOGO_SRC,result['html'])
        self.assertNotIn('bhm-banner-',result['html'])
        self.assertIn('Jeżeli nie chcesz otrzymywać',result['text'])

    def test_pagination_5676_persistent_500_plus_500(self):
        ids=self.contacts(5676);cid=self.campaign()
        response=self.client.get(f'/campaigns/{cid}/recipients')
        self.assertEqual(response.text.count('data-recipient value='),500)
        self.assertIn('Strona 1 / 12',response.text)
        self.assertEqual(update_selection(cid,ids[:500],ids[:500]),500)
        self.assertEqual(update_selection(cid,ids[500:1000],ids[500:1000]),1000)
        # Refresh, change filter, go back: the DB remains canonical.
        self.assertIn('1000</span>',self.client.get(f'/campaigns/{cid}/recipients?page=2').text)
        self.assertIn('1000</span>',self.client.get(f'/campaigns/{cid}/recipients?search=qa000&language=').text)
        with self.assertRaises(ValueError):update_selection(cid,[ids[1000]],[ids[1000]])
        self.assertEqual(update_selection(cid,[ids[0]],[],remove=True),999)
        self.assertEqual(update_selection(cid,[ids[1000]],[ids[1000]]),1000)
        self.assertEqual(update_selection(cid,[],[],clear=True),0)
        self.assertEqual(self.row('SELECT COUNT(*) AS n FROM contacts')['n'],5676)

    def test_selection_exclusions_duplicates_and_backend_limit(self):
        ids=self.contacts(1001);cid=self.campaign()
        with db.get_connection() as conn:
            for i,status in zip(ids[:3],('unsubscribed','invalid','bounced')):conn.execute('UPDATE contacts SET status=? WHERE id=?',(status,i))
        self.assertEqual(update_selection(cid,ids[:5],ids[:5]+[ids[3]]),2)
        with self.assertRaises(ValueError):mailer.prepare_campaign_send(cid,ids)
        result=mailer.prepare_campaign_send(cid,ids[:5]+[ids[3]])
        self.assertEqual(result['recipient_count'],2)
        with self.assertRaises(ValueError):mailer.prepare_campaign_send(cid,ids[:5])

    def test_selection_add_is_explicit_additive_and_idempotent(self):
        ids=self.contacts(3);cid=self.campaign()
        url=f'/campaigns/{cid}/selection'
        # Stale tabs can submit the same visible page with different checked rows.
        for checked, expected in ((ids[:1],1),(ids[1:2],2),(ids[:2],2),([],2)):
            response=self.client.post(url,data={'visible':','.join(map(str,ids)),
                'checked':','.join(map(str,checked)),'action':'add'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['selected_count'],expected)
        state=self.client.get(url)
        self.assertEqual(state.json()['selected_ids'],ids[:2])
        self.assertEqual(state.headers['cache-control'],'no-store')
        self.assertEqual(self.row('SELECT COUNT(*) n FROM email_sends')['n'],0)

    def test_selection_atomic_concurrent_limit(self):
        ids=self.contacts(1500);cid=self.campaign()
        update_selection(cid,ids[:500],ids[:500])
        barrier=threading.Barrier(2)
        def add(part):
            barrier.wait()
            try:return update_selection(cid,part,part)
            except ValueError:return 'limit'
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(add,part) for part in (ids[500:1000],ids[1000:1500])]
            outcomes=[f.result() for f in futures]
        self.assertCountEqual(outcomes,[1000,'limit'])
        self.assertEqual(self.client.get(f'/campaigns/{cid}/selection').json()['selected_count'],1000)

    def test_selection_clear_requires_confirmation_and_stays_campaign_scoped(self):
        ids=self.contacts(3);cid=self.campaign();other=self.campaign()
        update_selection(cid,ids,ids);update_selection(other,ids,ids)
        url=f'/campaigns/{cid}/selection'
        self.assertEqual(self.client.post(url,data={'clear':'1'}).status_code,400)
        self.assertEqual(self.client.get(url).json()['selected_count'],3)
        self.assertEqual(self.client.post(url,data={'action':'clear','confirm_clear':'1'}).json()['selected_count'],0)
        self.assertEqual(self.client.get(f'/campaigns/{other}/selection').json()['selected_count'],3)

    def test_selection_single_contact_reload_summary_and_remove(self):
        ids=self.contacts(1);cid=self.campaign()
        with db.get_connection() as conn:
            conn.execute("UPDATE contacts SET email='marcin@example.test' WHERE id=?",(ids[0],))
        url=f'/campaigns/{cid}'
        self.assertIn('marcin@example.test',self.client.get(url+'/recipients?search=marcin').text)
        response=self.client.post(url+'/selection',data={'visible':str(ids[0]),'checked':str(ids[0])})
        self.assertEqual(response.json()['selected_count'],1)
        html=self.client.get(url+'/recipients?search=marcin').text
        self.assertIn('data-membership>Dodano',html)
        summary=self.client.get(url+'/summary')
        self.assertEqual(summary.status_code,200)
        self.assertIn('data-summary-count>1 / 1000',summary.text)
        self.assertIn('marcin@example.test',summary.text)
        response=self.client.post(url+'/selection/remove',data={'contact_id':str(ids[0])})
        self.assertIn('data-summary-count>0 / 1000',response.text)
        self.assertEqual(self.row('SELECT COUNT(*) n FROM contacts')['n'],1)
        self.assertEqual(self.row('SELECT COUNT(*) n FROM email_sends')['n'],0)

    def test_selection_filters_and_statuses_do_not_delete_saved_rows(self):
        ids=self.contacts(4);cid=self.campaign();update_selection(cid,ids,ids)
        with db.get_connection() as conn:
            for i,status in zip(ids[:3],('unsubscribed','bounced','invalid')):
                conn.execute('UPDATE contacts SET status=? WHERE id=?',(status,i))
        url=f'/campaigns/{cid}'
        for query in ('?search=missing','?selected_only=1','?page=2','?language=en','?active_only=0'):
            self.assertEqual(self.client.get(url+'/recipients'+query).status_code,200)
        state=self.client.get(url+'/selection').json()
        self.assertEqual(state['selected_count'],4);self.assertEqual(state['eligible_count'],1)
        html=self.client.get(url+'/summary').text
        self.assertEqual(html.count('— wykluczony z wysyłki'),3)
        self.assertIn('data-summary-count>4 / 1000',html)

    def test_selection_invalid_api_requests_leave_state_intact(self):
        ids=self.contacts(501);cid=self.campaign();update_selection(cid,ids[:1],ids[:1])
        url=f'/campaigns/{cid}/selection'
        for form in ({'visible':'bad','checked':'1'}, {'visible':str(ids[0]),'checked':str(ids[1])},
                     {'visible':','.join(map(str,ids)),'checked':''}, {'action':'replace'}):
            self.assertEqual(self.client.post(url,data=form).status_code,400)
            self.assertEqual(self.client.get(url).json()['selected_ids'],ids[:1])

    def test_twenty_second_start_spacing_and_dry_run(self):
        cid,ids=self.prepare(4,mode='dry_run')
        attempts=[]
        for i in range(62):
            self.engine.tick()
            attempts.append(self.row('SELECT COUNT(*) AS n FROM email_sends WHERE status="dry_run"')['n'])
            self.clock.advance(1)
        self.assertEqual([i for i,n in enumerate(attempts) if i==0 or n!=attempts[i-1]],[0,20,40,60])
        self.assertEqual(self.starts,[])
        with db.get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM contacts WHERE last_sent_at IS NOT NULL').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM email_sends WHERE sent_at IS NOT NULL OR accepted_at IS NOT NULL').fetchone()[0],0)

    def test_many_hours_clock_breaks_and_no_duplicates(self):
        cid,ids=self.prepare(1000)
        breaks=[]
        previous='running'
        for second in range(0,30000,20):
            self.engine.tick()
            state=self.row('SELECT state FROM campaign_execution')['state']
            if state=='auto_break' and previous!='auto_break':breaks.append(self.clock())
            if previous=='auto_break' and state=='running':self.assertEqual(self.clock()-breaks[-1],300)
            previous=state
            if state=='completed':break
            self.clock.advance(20)
        self.assertEqual(len(self.starts),1000)
        gaps=[b-a for a,b in zip(self.starts,self.starts[1:])]
        self.assertTrue(all(g>=20 for g in gaps))
        self.assertEqual(min(gaps),20)
        self.assertEqual(breaks[:2],[1001800.,1003900.])
        self.assertGreaterEqual(len(breaks),5)
        self.assertEqual(self.row('SELECT MAX(attempt_count) AS n FROM email_sends')['n'],1)
        self.assertEqual(self.row('SELECT COUNT(*) AS n FROM contacts WHERE last_sent_at IS NOT NULL')['n'],1000)
        # Evidence is emitted to the test log, never operational history.
        print(json.dumps({'simulation':'1000 fake SMTP','attempts':len(self.starts),'min_gap':min(gaps),'max_gap':max(gaps),'break_starts':breaks,'elapsed':second}))

    def test_manual_pause_resume_and_cooldown(self):
        cid,ids=self.prepare()
        self.engine.tick();self.clock.advance(5)
        worker.pause(cid,self.clock())
        active=self.row('SELECT active_seconds FROM campaign_execution')['active_seconds']
        self.clock.advance(500);self.engine.tick()
        self.assertEqual(len(self.starts),1)
        self.assertEqual(self.row('SELECT active_seconds FROM campaign_execution')['active_seconds'],active)
        worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(len(self.starts),2)
        worker.pause(cid,self.clock());worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(len(self.starts),2)

    def test_manual_pause_during_auto_break(self):
        cid,ids=self.prepare()
        with db.get_connection() as conn:conn.execute('UPDATE campaign_execution SET cycle_seconds=1800')
        self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'auto_break')
        self.clock.advance(30);worker.pause(cid,self.clock())
        worker.resume(cid,self.clock());self.engine.tick()
        self.assertFalse(self.starts)
        worker.pause(cid,self.clock());self.clock.advance(400);self.engine.tick()
        self.assertFalse(self.starts)
        worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(len(self.starts),1)
        self.assertEqual(self.row('SELECT cycle_seconds FROM campaign_execution')['cycle_seconds'],0)

    def test_pause_while_inflight_and_idempotent_reservation(self):
        cid,ids=self.prepare()
        gate=threading.Event();release=threading.Event()
        def delayed(*a,**kw):gate.set();release.wait(5);return self.fake_send(*a,**kw)
        self.engine.sender=delayed
        thread=threading.Thread(target=self.engine.tick);thread.start();self.assertTrue(gate.wait(2))
        self.engine.tick();worker.pause(cid,self.clock())
        self.assertEqual(self.row('SELECT COUNT(*) AS n FROM email_sends WHERE status="sending"')['n'],1)
        release.set();thread.join(5)
        self.clock.advance(50);self.engine.tick()
        self.assertEqual(len(self.starts),1)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'manual_paused')

    def test_ui_responds_while_smtp_is_blocked(self):
        cid,ids=self.prepare(1000)
        entered=threading.Event();release=threading.Event()
        def delayed(*args,**kwargs):
            entered.set();release.wait(8)
            return self.fake_send(*args,**kwargs)
        self.engine.sender=delayed
        thread=threading.Thread(target=self.engine.tick);thread.start()
        try:
            self.assertTrue(entered.wait(2))
            start=time.perf_counter()
            response=self.client.get(f'/campaigns/{cid}/status.json')
            contacts=self.client.get('/contacts?search=qa000')
            self.assertLess(time.perf_counter()-start,4)
            self.assertEqual(response.status_code,200);self.assertEqual(contacts.status_code,200)
            self.assertEqual(response.json()['current_email'],'qa00000@example.test')
            self.assertEqual(response.json()['counts']['sending'],1)
        finally:
            release.set();thread.join(10)

    def test_slow_smtp_uses_start_to_start_interval(self):
        cid,ids=self.prepare()
        def slow(*args,**kwargs):
            response=self.fake_send(*args,**kwargs);self.clock.advance(35);return response
        self.engine.sender=slow
        self.engine.tick();self.engine.tick()
        self.assertEqual(self.starts,[1000000.,1000035.])

    def test_two_campaign_starts_and_process_owners(self):
        ids=self.contacts();a=self.campaign();b=self.campaign()
        def start(cid):
            try:return mailer.prepare_campaign_send(cid,ids)['started']
            except ValueError:return False
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(start,[a,b]))
        self.assertEqual(results.count(True),1)
        first=worker.Manager();second=worker.Manager()
        try:
            first.start();second.start()
            self.assertTrue(first.available);self.assertFalse(second.available)
        finally:first.shutdown();second.shutdown()

    def test_restart_between_messages_needs_resume(self):
        cid,ids=self.prepare();self.engine.tick()
        worker.recover(self.clock());self.clock.advance(50);self.engine.tick()
        self.assertEqual(len(self.starts),1)
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'interrupted')
        worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(len(self.starts),2)
        self.assertEqual(self.row('SELECT attempt_count FROM email_sends ORDER BY id')['attempt_count'],1)

    def test_restart_uncertain_requires_evidence(self):
        cid,ids=self.prepare()
        with db.get_connection() as conn:conn.execute("UPDATE email_sends SET status='sending',attempt_count=1 WHERE id=(SELECT MIN(id) FROM email_sends)")
        worker.recover(self.clock())
        send=self.row('SELECT * FROM email_sends ORDER BY id')
        self.assertEqual(send['status'],'delivery_unknown')
        with self.assertRaises(ValueError):worker.resume(cid,self.clock())
        with self.assertRaises(ValueError):worker.resolve_uncertain(send['id'],'retry_not_accepted','Confirmed trace evidence',False,self.clock())
        worker.resolve_uncertain(send['id'],'cancel','Operator chooses no retry',now=self.clock())
        worker.resume(cid,self.clock());self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM email_sends ORDER BY id')['status'],'cancelled')

    def test_transport_timeout_is_uncertain_no_retry(self):
        cid,ids=self.prepare()
        def fail(*a,**kw):raise TimeoutError('SMTP transport timeout')
        self.engine.sender=fail;self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM email_sends ORDER BY id')['status'],'delivery_unknown')
        self.assertEqual(self.row('SELECT outcome_uncertain FROM email_sends ORDER BY id')['outcome_uncertain'],1)
        self.clock.advance(1000);self.engine.tick()
        with self.assertRaises(ValueError):worker.resume(cid,self.clock())

    def test_rate_limit_4xx_pauses_with_cooldown(self):
        cid,ids=self.prepare()
        def fail(*a,**kw):raise smtplib.SMTPDataError(451,b'temporary rate limit')
        self.engine.sender=fail;self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM email_sends ORDER BY id')['status'],'rate_limited')
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'auto_cooldown')
        self.engine.sender=self.fake_send;self.engine.tick()
        self.assertFalse(self.starts)
        # Tick regularly during provider wait, since a real worker also checks liveness.
        for _ in range(900):self.clock.advance(1);self.engine.tick()
        self.assertEqual(len(self.starts),1)
        with db.get_connection() as conn:
            self.assertEqual([r[0] for r in conn.execute('SELECT status FROM send_attempt_history ORDER BY id')],['rate_limited','accepted_by_smtp'])

    def test_permanent_recipient_failure_continues(self):
        cid,ids=self.prepare()
        def fail(*a,**kw):raise smtplib.SMTPRecipientsRefused({a[1]:(550,b'no mailbox')})
        self.engine.sender=fail;self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM email_sends ORDER BY id')['status'],'smtp_failed')
        self.assertEqual(self.row('SELECT status FROM contacts ORDER BY id')['status'],'bounced')
        self.engine.sender=self.fake_send;self.clock.advance(20);self.engine.tick()
        self.assertEqual(len(self.starts),1)

    def test_rolling_limit_and_live_exclusion(self):
        cid,ids=self.prepare()
        with db.get_connection() as conn:
            send=conn.execute('SELECT id FROM email_sends LIMIT 1').fetchone()[0]
            conn.executemany('INSERT INTO smtp_attempts(send_id,started) VALUES(?,?)',[(send,self.clock()-10)]*20)
        self.engine.tick();self.assertFalse(self.starts)
        self.assertEqual(self.row('SELECT next_attempt FROM campaign_execution')['next_attempt'],self.clock()+290)
        with db.get_connection() as conn:conn.execute("UPDATE contacts SET status='unsubscribed' WHERE id=?",(ids[0],))
        self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM email_sends ORDER BY id')['status'],'skipped_unsubscribed')

    def test_invalid_recipient_553_preserves_contact_semantics(self):
        cid,ids=self.prepare()
        def fail(*args,**kwargs):raise smtplib.SMTPRecipientsRefused({args[1]:(553,b'invalid recipient')})
        self.engine.sender=fail;self.engine.tick()
        self.assertEqual(self.row('SELECT status FROM contacts ORDER BY id')['status'],'invalid')
        self.assertEqual(self.row('SELECT status FROM email_sends ORDER BY id')['status'],'smtp_failed')

    def test_recovery_sleep_detection(self):
        cid,ids=self.prepare();self.engine.tick();self.clock.advance(121);self.engine.tick()
        self.assertEqual(self.row('SELECT state FROM campaign_execution')['state'],'interrupted')
        self.assertEqual(len(self.starts),1)

    def test_smtp_identity_change_blocks_resume(self):
        cid,ids=self.prepare();worker.pause(cid,self.clock())
        with patch.object(mailer,'get_mail_settings',return_value=replace(settings(),smtp_user='different@example.test')):
            with self.assertRaises(ValueError):worker.resume(cid,self.clock())

    def test_signed_unsubscribe_and_local_notification(self):
        ids=self.contacts(1);cid=self.campaign()
        url=mailer.build_public_unsubscribe_url(settings(),'qa00000@example.test','token0','pl',cid)
        params={k:v[0] for k,v in parse_qs(urlsplit(url).query).items()}
        expected=hmac.new(b'test-signature',f"{params['email']}|{params['token']}|pl|{cid}|{params['ts']}".encode(),hashlib.sha256).hexdigest()
        self.assertEqual(params['sig'],expected)
        with patch.object(main,'maybe_send_unsubscribe_notification') as notification:
            response=self.client.get(f'/unsubscribe/token0?c={cid}')
            self.assertEqual(response.status_code,200);notification.assert_called_once()
        self.assertEqual(self.row('SELECT status FROM contacts')['status'],'unsubscribed')
        self.assertEqual(self.row('SELECT COUNT(*) AS n FROM unsubscribe_events')['n'],1)

    def test_trace_export_snapshot_preservation(self):
        cid,ids=self.prepare(1);self.engine.tick()
        before=self.row('SELECT html_snapshot,text_snapshot FROM email_sends')
        report=main.import_message_trace_csv(cid,'Recipient,Subject,Status\nqa00000@example.test,Temat odbiorcy,Delivered\n')
        self.assertEqual(report['matched'],1)
        self.assertEqual(self.row('SELECT status FROM email_sends')['status'],'delivered_by_trace')
        self.assertEqual(before,self.row('SELECT html_snapshot,text_snapshot FROM email_sends'))
        response=self.client.get(f'/campaigns/{cid}/export.csv')
        self.assertEqual(response.status_code,200);self.assertIn('Delivered by Trace',response.text)
        for state in ('pending','sending','dry_run'):
            self.assertEqual(main.trace_status_to_send_status('Delivered',state)[0],state)

    def test_additive_migration_preserves_records_and_is_idempotent(self):
        cid,ids=self.prepare(1);self.engine.tick()
        with db.get_connection() as conn:
            before={t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in ('contacts','campaigns','email_sends','unsubscribe_events')}
            conn.execute('DROP TABLE recovery_decisions')
        db.init_db();db.init_db()
        with db.get_connection() as conn:
            after={t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in before}
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(before,after)

    def test_monitor_payload_and_routes(self):
        cid,ids=self.prepare();self.engine.tick()
        payload=worker.execution_payload(cid,self.clock())
        self.assertEqual(payload['counts']['accepted'],1);self.assertEqual(payload['counts']['pending'],2)
        self.assertEqual(payload['next_email'],'qa00001@example.test');self.assertEqual(payload['current_email'],'')
        worker.pause(cid,self.clock());payload=worker.execution_payload(cid,self.clock())
        self.assertIsNone(payload['eta_seconds']);self.assertTrue(payload['eta_uncertain'])
        response=self.client.get(f'/campaigns/{cid}/monitor')
        self.assertEqual(response.status_code,200);self.assertNotIn('<table',response.text)
        self.assertNotIn('qa00001@example.test',response.text)
        response=self.client.get(f'/campaigns/{cid}/status.json')
        self.assertEqual(response.json()['counts']['accepted'],1)

    def test_selection_post_and_final_recheck(self):
        ids=self.contacts();cid=self.campaign()
        response=self.client.post(f'/campaigns/{cid}/selection',data={'visible':','.join(map(str,ids)),'checked':','.join(map(str,ids))})
        self.assertEqual(response.json()['selected_count'],3)
        response=self.client.post(f'/campaigns/{cid}/recipients')
        self.assertIn('Podsumowanie odbiorców',response.text)
        fingerprint=selection_fingerprint(ids)
        with db.get_connection() as conn:conn.execute("UPDATE contacts SET status='unsubscribed' WHERE id=?",(ids[0],))
        response=self.client.post(f'/campaigns/{cid}/recipients',data={'confirmed':'1','fingerprint':fingerprint,'mode':'dry_run'},follow_redirects=False)
        self.assertIn('Selekcja',response.headers['location'])
        self.assertEqual(self.row('SELECT COUNT(*) AS n FROM email_sends')['n'],0)

    def test_final_start_redirects_to_separate_monitor_and_snapshots_lock(self):
        ids=self.contacts(1);cid=self.campaign();update_selection(cid,ids,ids)
        with patch.object(worker.Manager,'available',new_callable=PropertyMock,return_value=True):
            response=self.client.post(f'/campaigns/{cid}/recipients',data=dict(confirmed='1',fingerprint=selection_fingerprint(ids),mode='dry_run'),follow_redirects=False)
        self.assertEqual(response.status_code,303)
        self.assertEqual(response.headers['location'],f'/campaigns/{cid}/monitor')
        before=self.row('SELECT html_snapshot,text_snapshot FROM email_sends')
        self.client.post(f'/campaigns/{cid}/reopen')
        self.assertEqual(self.row('SELECT status FROM campaigns')['status'],'sending')
        self.assertEqual(before,self.row('SELECT html_snapshot,text_snapshot FROM email_sends'))

    def test_restart_preserves_remaining_automatic_break(self):
        cid,ids=self.prepare()
        with db.get_connection() as conn:conn.execute('UPDATE campaign_execution SET cycle_seconds=1800')
        self.engine.tick();self.clock.advance(60);worker.recover(self.clock());worker.resume(cid,self.clock())
        self.engine.tick();self.assertFalse(self.starts)
        self.clock.advance(239);self.engine.tick();self.assertFalse(self.starts)
        self.clock.advance(1);self.engine.tick();self.assertEqual(len(self.starts),1)

    def test_history_attempt_ledger_and_contact_history_routes(self):
        cid,ids=self.prepare(1);self.engine.tick()
        self.assertIn('Dziennik prób',self.client.get(f'/history/{cid}').text)
        response=self.client.get(f'/contacts/{ids[0]}/history')
        self.assertEqual(response.status_code,200)
        self.assertIn('Accepted by SMTP',response.text)

    def test_queued_notification_shares_worker_and_interval(self):
        ids=self.contacts(1)
        with db.get_connection() as conn:
            eid=conn.execute("INSERT INTO unsubscribe_events(contact_id,email,token,created_at) VALUES(?,'qa00000@example.test','token0',?)",(ids[0],db.utc_now())).lastrowid
            self.assertFalse(mailer.maybe_send_unsubscribe_notification(conn,eid,'qa00000@example.test',None))
        self.assertEqual(self.row('SELECT notification_status FROM unsubscribe_events')['notification_status'],'queued')
        self.engine.tick()
        self.assertEqual(self.row('SELECT notification_sent FROM unsubscribe_events')['notification_sent'],1)
        self.assertEqual(len(self.starts),1)
        cid=self.campaign()
        mailer.prepare_campaign_send(cid,ids,'smtp')
        with db.get_connection() as conn:conn.execute('UPDATE campaign_execution SET started=?,updated=?',(self.clock(),self.clock()))
        self.engine.tick();self.assertEqual(len(self.starts),1)
        self.clock.advance(20);self.engine.tick();self.assertEqual(len(self.starts),2)

    def test_xlsx_import_and_contact_history(self):
        import openpyxl
        from app.importer import import_from_xlsx
        book=openpyxl.Workbook();sheet=book.active;sheet.title='PL'
        sheet.append(['Email','Company name']);sheet.append(['imported@example.test','Synthetic'])
        path=self.test_root/'fixture.xlsx';book.save(path);book.close()
        report=import_from_xlsx(path,'PL')
        self.assertEqual(report.added,1)
        self.assertEqual(import_from_xlsx(path,'PL').added,0)
        self.assertEqual(self.client.get('/contacts?search=imported').status_code,200)

    def test_post_origin_guard(self):
        self.assertEqual(self.client.post('/editor/sanitize',data={'html':'test'},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/editor/sanitize').status_code,405)

    def test_actual_baseline_schema_migration(self):
        legacy_path=self.test_root/'legacy.sqlite3'
        schema=Path(__file__).parent/'fixtures'/'baseline_v13.sql'
        conn=sqlite3.connect(legacy_path)
        conn.executescript(schema.read_text(encoding='utf-8'))
        conn.execute("INSERT INTO contacts(id,email,country_group,language,status,created_at,updated_at) VALUES(1,'old@example.test','PL','pl','unsubscribed','2020-01-01','2020-01-01')")
        conn.execute("INSERT INTO campaigns(id,name,subject,language,body,html,text,status,created_at) VALUES(1,'Legacy','Subject','pl','Old body','<p>Old</p>','Old text','completed','2020-01-01')")
        conn.execute("INSERT INTO email_sends(campaign_id,contact_id,email,language,subject,html_snapshot,text_snapshot,status,created_at) VALUES(1,1,'old@example.test','pl','Subject','<p>Old snapshot</p>','Old snapshot','sent','2020-01-01')")
        conn.execute("INSERT INTO unsubscribe_events(contact_id,email,token,created_at) VALUES(1,'old@example.test','old-token','2020-01-01')")
        conn.commit()
        columns={t:[r[1] for r in conn.execute('PRAGMA table_info('+t+')')] for t in ('contacts','campaigns','email_sends','unsubscribe_events')}
        before={t:conn.execute('SELECT '+','.join(columns[t])+' FROM '+t).fetchall() for t in columns}
        backup_path=self.test_root/'legacy-backup.sqlite3'
        backup=sqlite3.connect(backup_path);conn.backup(backup);backup.close()
        backup_hash=hashlib.sha256(backup_path.read_bytes()).hexdigest()
        conn.close()
        with patch.object(db,'DB_PATH',legacy_path):
            db.init_db();db.init_db()
            with db.get_connection() as conn:
                after={t:[tuple(r) for r in conn.execute('SELECT '+','.join(columns[t])+' FROM '+t)] for t in columns}
                self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertFalse(conn.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(before,after)
        self.assertEqual(backup_hash,hashlib.sha256(backup_path.read_bytes()).hexdigest())

    def test_contact_import_edit_regression(self):
        from app.importer import import_from_paste,import_from_xlsx
        report=import_from_paste('person@example.test\ninvalid-input', 'PL')
        self.assertEqual(report.added,1)
        row=self.row('SELECT * FROM contacts')
        self.assertEqual(self.client.get(f"/contacts/{row['id']}/edit").status_code,200)
        response=self.client.post(f"/contacts/{row['id']}/edit",data=dict(email='updated@example.test',country_group='PL',language='pl',status='active'),follow_redirects=False)
        self.assertEqual(response.status_code,303)
        self.assertEqual(self.row('SELECT email FROM contacts')['email'],'updated@example.test')


if __name__=='__main__':unittest.main()
