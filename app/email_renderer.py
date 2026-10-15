from __future__ import annotations

from html import escape
from pathlib import Path
import re


CONTACT_EMAIL = "info@bhm-chemicals.com"
EMAIL_LOGO_CID = "bhm-chemicals-logo"
EMAIL_LOGO_SRC = f"cid:{EMAIL_LOGO_CID}"
EMAIL_LOGO_FILENAME = "bhm-chemicals-logo.png"
EMAIL_LOGO_PATH = Path(__file__).resolve().parent / "static" / "assets" / EMAIL_LOGO_FILENAME
UNSUBSCRIBE_PLACEHOLDER = "[unsubscribe link generated per recipient]"
LEGACY_UNSUBSCRIBE_PLACEHOLDER = "{{ unsubscribe_url }}"

COMPANY_FOOTER_LINES = [
    "BHM Chemicals Sp. z o. o.",
    "Ul. Wrocławska 20",
    "67-100 Nowa Sól",
    "Poland",
    "Tel. +48 519 702 757 (office hours)",
    "Company registration no. (REGON) 389960282",
    "VAT no. (NIP) PL 9252134615",
    "KRS 0000922248",
]


def parse_products(products_text: str | None) -> list[str]:
    if not products_text:
        return []
    return [line.strip() for line in products_text.splitlines() if line.strip()]


def normalise_language(language: str | None) -> str:
    return "pl" if (language or "").lower() == "pl" else "en"


def preheader_from_body(body: str | None) -> str:
    compact = re.sub(r"\s+", " ", body or "").strip()
    return compact[:140] or "BHM Chemicals"


def body_paragraphs(body: str | None) -> list[str]:
    normalized = (body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [block.strip() for block in re.split(r"\n\s*\n+", normalized) if block.strip()]


def render_body_html(body: str | None) -> str:
    paragraphs = body_paragraphs(body)
    if not paragraphs:
        return ""
    rendered: list[str] = []
    for paragraph in paragraphs:
        lines = [escape(line.strip()) for line in paragraph.split("\n")]
        rendered.append(
            f"""
            <p style="margin:0 0 18px 0;color:#10212B;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.65;">
              {'<br>'.join(lines)}
            </p>
            """.strip()
        )
    return "\n".join(rendered)


def render_products_html(products: list[str], language: str) -> str:
    if not products:
        return ""
    title = "Wybrane produkty" if normalise_language(language) == "pl" else "Selected products"
    rows = []
    for product in products:
        rows.append(
            f"""
            <tr>
              <td style="padding:0 0 10px 0;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;border:1px solid #D9E1E8;background:#FFFFFF;">
                  <tr>
                    <td style="padding:14px 16px;color:#0B1F2A;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.45;">
                      {escape(product)}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            """.strip()
        )
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;margin:22px 0 6px 0;">
      <tr>
        <td style="padding:0 0 12px 0;color:#0B1F2A;font-family:Arial,Helvetica,sans-serif;font-size:17px;font-weight:bold;line-height:1.3;">
          {title}
        </td>
      </tr>
      {''.join(rows)}
    </table>
    """.strip()


def render_cta_html(label: str | None, url: str | None) -> str:
    if not label or not url:
        return ""
    return f"""
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;margin:26px 0 4px 0;">
      <tr>
        <td bgcolor="#0A6B3D" style="border-radius:4px;">
          <a href="{escape(url, quote=True)}" style="display:inline-block;padding:13px 20px;color:#FFFFFF;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;text-decoration:none;border-radius:4px;">
            {escape(label)}
          </a>
        </td>
      </tr>
    </table>
    """.strip()


def logo_is_available() -> bool:
    return EMAIL_LOGO_PATH.exists()


def render_text_brand_html() -> str:
    return """
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;width:100%;">
      <tr>
        <td valign="middle" style="color:#0B1F2A;font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:1.25;font-weight:bold;letter-spacing:0;">
          BHM Chemicals
        </td>
      </tr>
    </table>
    """.strip()


def render_logo_brand_html() -> str:
    if not logo_is_available():
        return render_text_brand_html()
    return f"""
    <img src="{EMAIL_LOGO_SRC}" width="260" alt="BHM Chemicals" style="display:block;width:260px;max-width:100%;height:auto;border:0;outline:none;text-decoration:none;">
    """.strip()


def render_brand_header_html() -> str:
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;background:#FFFFFF;">
      <tr>
        <td bgcolor="#0B1F2A" height="6" style="height:6px;font-size:0;line-height:0;">&nbsp;</td>
      </tr>
      <tr>
        <td style="padding:26px 30px 22px 30px;border-bottom:1px solid #D9E1E8;">
          {render_logo_brand_html()}
        </td>
      </tr>
    </table>
    """.strip()


def render_contact_html(language: str) -> str:
    text = (
        "Po więcej informacji prosimy o kontakt:"
        if normalise_language(language) == "pl"
        else "For more information, please contact us:"
    )
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;margin:18px 0 0 0;background:#F4F7F9;border:1px solid #D9E1E8;">
      <tr>
        <td style="padding:16px 18px;color:#10212B;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.55;">
          {text} <a href="mailto:{CONTACT_EMAIL}" style="color:#0A6B3D;text-decoration:underline;">{CONTACT_EMAIL}</a>
        </td>
      </tr>
    </table>
    """.strip()


def render_company_footer_html() -> str:
    escaped_lines = [escape(line) for line in COMPANY_FOOTER_LINES]
    first_line = escaped_lines[0]
    rest = "<br>".join(escaped_lines[1:])
    return f"""
    <p style="margin:0;color:#5B6B76;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;">
      <strong style="color:#0B1F2A;">{first_line}</strong><br>
      {rest}
    </p>
    """.strip()


def render_unsubscribe_html(language: str, unsubscribe_url: str) -> str:
    if normalise_language(language) == "pl":
        text = "Jeżeli nie chcesz otrzymywać kolejnych wiadomości, kliknij:"
        link_label = "Wypisz się"
    else:
        text = "If you no longer wish to receive these emails, click:"
        link_label = "Unsubscribe"
    return f"""
    <p style="margin:14px 0 0 0;color:#5B6B76;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;">
      {text} <a href="{escape(unsubscribe_url, quote=True)}" style="color:#0A6B3D;text-decoration:underline;">{link_label}</a>.
    </p>
    """.strip()


def render_footer(language: str, unsubscribe_url: str) -> str:
    return f"""
    {render_company_footer_html()}
    {render_unsubscribe_html(language, unsubscribe_url)}
    """.strip()


def render_email_html(
    language: str,
    subject: str | None,
    body: str | None,
    products: list[str] | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    unsubscribe_url: str = UNSUBSCRIBE_PLACEHOLDER,
) -> str:
    language = normalise_language(language)
    products = products or []
    headline = subject or ("Oferta BHM Chemicals" if language == "pl" else "BHM Chemicals offer")
    preheader = preheader_from_body(body)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(headline)}</title>
  </head>
  <body style="margin:0;padding:0;background:#F4F7F9;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;font-size:1px;line-height:1px;">
      {escape(preheader)}
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;background:#F4F7F9;">
      <tr>
        <td align="center" style="padding:28px 12px;">
          <table role="presentation" width="640" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px;border-collapse:collapse;background:#FFFFFF;border:1px solid #D9E1E8;">
            <tr>
              <td style="padding:0;">
                {render_brand_header_html()}
              </td>
            </tr>
            <tr>
              <td style="padding:34px 34px 12px 34px;">
                <h1 style="margin:0;color:#0B1F2A;font-family:Arial,Helvetica,sans-serif;font-size:27px;line-height:1.22;font-weight:bold;letter-spacing:0;">
                  {escape(headline)}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 34px 34px 34px;">
                {render_body_html(body)}
                {render_products_html(products, language)}
                {render_cta_html(cta_label, cta_url)}
                {render_contact_html(language)}
              </td>
            </tr>
            <tr>
              <td style="border-top:1px solid #D9E1E8;background:#F4F7F9;padding:24px 34px 28px 34px;">
                {render_footer(language, unsubscribe_url)}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def render_email_text(
    language: str,
    subject: str | None,
    body: str | None,
    products: list[str] | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    unsubscribe_url: str = UNSUBSCRIBE_PLACEHOLDER,
) -> str:
    language = normalise_language(language)
    products = products or []
    lines = ["BHM Chemicals"]
    if subject:
        lines.extend(["", subject])
    if body:
        lines.extend(["", body.strip()])
    if products:
        lines.extend(["", "Wybrane produkty:" if language == "pl" else "Selected products:"])
        lines.extend(f"- {product}" for product in products)
    if cta_label and cta_url:
        lines.extend(["", f"{cta_label}: {cta_url}"])

    if language == "pl":
        lines.extend(["", f"Po więcej informacji prosimy o kontakt: {CONTACT_EMAIL}"])
        unsubscribe_line = (
            f"Jeżeli nie chcesz otrzymywać kolejnych wiadomości, kliknij: Wypisz się. {unsubscribe_url}"
        )
    else:
        lines.extend(["", f"For more information, please contact us: {CONTACT_EMAIL}"])
        unsubscribe_line = (
            f"If you no longer wish to receive these emails, click: Unsubscribe. {unsubscribe_url}"
        )

    lines.extend(["", *COMPANY_FOOTER_LINES, "", unsubscribe_line])
    return "\n".join(lines).strip() + "\n"


def render_campaign_single(language: str, subject: str | None, body: str | None) -> dict[str, str]:
    return {
        "html": render_email_html(language, subject, body),
        "text": render_email_text(language, subject, body),
    }


def render_campaign_pair(
    subject_pl: str | None,
    subject_en: str | None,
    body_pl: str | None,
    body_en: str | None,
    products_text: str | None,
    cta_label_pl: str | None,
    cta_label_en: str | None,
    cta_url: str | None,
) -> dict[str, str]:
    products = parse_products(products_text)
    return {
        "html_pl": render_email_html("pl", subject_pl, body_pl, products, cta_label_pl, cta_url),
        "html_en": render_email_html("en", subject_en, body_en, products, cta_label_en, cta_url),
        "text_pl": render_email_text("pl", subject_pl, body_pl, products, cta_label_pl, cta_url),
        "text_en": render_email_text("en", subject_en, body_en, products, cta_label_en, cta_url),
    }
