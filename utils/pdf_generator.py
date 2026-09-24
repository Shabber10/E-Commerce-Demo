from io import BytesIO
from xhtml2pdf import pisa

def generate_pdf(template_html):
    """
    Converts an HTML string into PDF bytes using xhtml2pdf.
    Returns the in-memory BytesIO object, or None if conversion failed.
    """
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(template_html, dest=pdf)

    if pisa_status.err:
        return None
    return pdf
