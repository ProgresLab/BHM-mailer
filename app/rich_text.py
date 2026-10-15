"""Small, deliberately restricted email document format; never arbitrary HTML."""
from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

import bleach

TAGS = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'span', 'div'}
SIZES = {'14px', '16px', '18px', '22px', '28px'}


def safe_url(value: str, *, mailto: bool = False) -> str:
    value = (value or '').strip()
    if not value or re.search(r'[\x00-\x20\x7f<>"\\]', value):
        return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {'https', 'http'} and parsed.hostname and not parsed.username and not parsed.password:
            return value
        if mailto and parsed.scheme == 'mailto' and re.fullmatch(r'[^@\s?]+@[^@\s?]+\.[^@\s?]+', parsed.path):
            return value
    except ValueError:
        pass
    return ''


class CorporateCSS:
    def sanitize_css(self, style):
        allowed = []
        for item in style.lower().split(';'):
            key, _, value = item.partition(':')
            key, value = key.strip(), value.strip()
            if (key == 'font-size' and value in SIZES or
                key == 'font-weight' and value in {'bold', '700'} or
                key == 'font-style' and value == 'italic' or
                key == 'text-decoration' and value == 'underline'):
                allowed.append(f'{key}:{value}')
        return ';'.join(allowed)


def attribute(tag, name, value):
    if tag == 'a' and name == 'href':
        return bool(safe_url(value, mailto=True))
    if name == 'style':
        return True
    return tag == 'ul' and name == 'data-list' and value == 'check'


def sanitize_html(value: str) -> str:
    # Strip active-content bodies as well as the tags. Bleach repairs malformed markup.
    value = re.sub(r'<(script|style|iframe|object)\b[^>]*>.*?</\1\s*>', '', value, flags=re.I | re.S)
    # Native browser fontSize uses <font>; convert only our five choices.
    value = re.sub(r'<font\s+size=["\']?([1-7])["\']?[^>]*>',
                   lambda m: f'<span style="font-size:{dict(zip("1234567", ["14px", "14px", "16px", "18px", "22px", "28px", "28px"]))[m[1]]}">', value, flags=re.I)
    value = re.sub(r'</font>', '</span>', value, flags=re.I)
    return bleach.clean(value, tags=TAGS, attributes=attribute, protocols={'http', 'https', 'mailto'},
                        strip=True, css_sanitizer=CorporateCSS())


class TextDocument(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in {'p', 'div', 'h2', 'h3', 'br', 'ul', 'ol'}:
            self.parts.append('\n')
        if tag == 'li':
            self.parts.append('\n- ')
        if tag == 'a':
            self.links.append(dict(attrs).get('href', ''))

    def handle_endtag(self, tag):
        if tag in {'p', 'div', 'h2', 'h3', 'li', 'ul', 'ol'}:
            self.parts.append('\n')
        if tag == 'a' and self.links:
            url = self.links.pop()
            if url:
                self.parts.append(f' ({url})')

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = TextDocument()
    parser.feed(sanitize_html(value))
    return re.sub(r'\n[ \t]*\n[ \t]*\n+', '\n\n', ''.join(parser.parts)).strip()


def legacy_to_html(value: str) -> str:
    return '<p>' + escape(value or '').replace('\n', '<br>') + '</p>'


class EmailDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.checks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = attrs.pop('style', '')
        if tag in {'p', 'div'}:
            style += ';margin:0 0 16px;line-height:1.65'
        elif tag in {'ul', 'ol'}:
            self.checks.append(tag == 'ul' and attrs.pop('data-list', '') == 'check')
            style += ';padding-left:24px;margin:0 0 18px'
            if self.checks[-1]:
                style += ';list-style:none;padding-left:0'
        elif tag == 'li':
            style += ';margin:0 0 8px;line-height:1.65'
        elif tag == 'a':
            style += ';color:#0A6B3D;text-decoration:underline'
        elif tag in {'h2', 'h3'}:
            style += ';color:#11263A;margin:24px 0 14px;line-height:1.3'
        attr_text = ''.join(f' {k}="{escape(v, quote=True)}"' for k, v in attrs.items())
        if style:
            attr_text += f' style="{escape(style.strip(";"), quote=True)}"'
        self.parts.append(f'<{tag}{attr_text}>')
        if tag == 'li' and self.checks and self.checks[-1]:
            self.parts.append('<span style="color:#0A6B3D;font-weight:bold">&#10003;&nbsp; </span>')

    def handle_endtag(self, tag):
        self.parts.append(f'</{tag}>')
        if tag in {'ul', 'ol'} and self.checks:
            self.checks.pop()

    def handle_data(self, data):
        self.parts.append(escape(data))


def email_body(value: str) -> str:
    parser = EmailDocument()
    parser.feed(sanitize_html(value))
    return ''.join(parser.parts)
