-- Source: git 37ce3a788ba1cd01476a016c8113db52bccd45e9 app/db.py; schema only, no operational data.
CREATE TABLE campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                language TEXT NULL CHECK(language IN ('pl', 'en')),
                subject TEXT NULL,
                body TEXT NULL,
                html TEXT NULL,
                text TEXT NULL,
                subject_pl TEXT NULL,
                subject_en TEXT NULL,
                body_pl TEXT NULL,
                body_en TEXT NULL,
                html_pl TEXT NULL,
                html_en TEXT NULL,
                text_pl TEXT NULL,
                text_en TEXT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'draft', 'approved', 'sending', 'completed',
                    'completed_with_errors', 'stopped'
                )),
                created_at TEXT NOT NULL,
                approved_at TEXT NULL,
                completed_at TEXT NULL
            );
CREATE TABLE contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                company_name TEXT NULL,
                contact_name TEXT NULL,
                industry TEXT NULL,
                country_group TEXT NOT NULL CHECK(country_group IN ('PL', 'INTERNATIONAL')),
                language TEXT NOT NULL CHECK(language IN ('pl', 'en')),
                status TEXT NOT NULL CHECK(status IN ('active', 'unsubscribed', 'bounced', 'invalid')),
                source TEXT NULL,
                source_sheet TEXT NULL,
                consent_status TEXT NULL,
                notes TEXT NULL,
                unsubscribe_token TEXT UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_sent_at TEXT NULL
            );
CREATE TABLE email_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                language TEXT NOT NULL,
                subject TEXT NOT NULL,
                html_snapshot TEXT NOT NULL,
                text_snapshot TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'pending', 'sending', 'accepted_by_smtp', 'smtp_failed',
                    'rate_limited', 'delivery_pending', 'delivered_by_trace',
                    'failed_by_trace', 'quarantined_by_trace', 'bounced_later',
                    'delivery_unknown', 'skipped_unsubscribed', 'skipped_invalid',
                    'skipped_duplicate', 'cancelled', 'dry_run', 'sent', 'failed',
                    'bounced', 'invalid'
                )),
                smtp_response TEXT NULL,
                error_message TEXT NULL,
                smtp_user TEXT NULL,
                header_from TEXT NULL,
                reply_to TEXT NULL,
                envelope_from TEXT NULL,
                envelope_to TEXT NULL,
                message_id TEXT NULL,
                sent_at TEXT NULL,
                created_at TEXT NOT NULL, smtp_code TEXT NULL, smtp_message_id TEXT NULL, provider_message_id TEXT NULL, attempt_count INTEGER DEFAULT 0, started_at TEXT NULL, accepted_at TEXT NULL, final_status_at TEXT NULL, last_checked_at TEXT NULL, trace_status TEXT NULL, trace_detail TEXT NULL, trace_source TEXT NULL, last_error TEXT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(contact_id) REFERENCES contacts(id)
            );
CREATE TABLE unsubscribe_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                token TEXT NOT NULL,
                source_campaign_id INTEGER NULL,
                created_at TEXT NOT NULL,
                notification_sent INTEGER DEFAULT 0,
                FOREIGN KEY(contact_id) REFERENCES contacts(id),
                FOREIGN KEY(source_campaign_id) REFERENCES campaigns(id)
            );
