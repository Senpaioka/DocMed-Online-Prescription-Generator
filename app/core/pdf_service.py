import os
import io
import logging
from flask import render_template, make_response, current_app

# Windows MSYS2 / GTK DLL path initialization for WeasyPrint
if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
    msys2_mingw_bin = r'C:\msys64\mingw64\bin'
    if os.path.exists(msys2_mingw_bin):
        try:
            os.add_dll_directory(msys2_mingw_bin)
        except Exception as e:
            logging.warning(f"Could not add DLL directory {msys2_mingw_bin}: {e}")

_WEASYPRINT_AVAILABLE = False
try:
    import weasyprint
    _WEASYPRINT_AVAILABLE = True
except Exception as e:
    logging.warning(f"WeasyPrint import failed: {e}. Will fallback to xhtml2pdf if needed.")


def generate_pdf_bytes(template_name: str, context: dict, base_url: str = None) -> bytes:
    """
    Renders the given Jinja template with context and converts it to PDF bytes.
    Uses WeasyPrint for modern, beautiful CSS3 paged media rendering,
    with a graceful fallback to xhtml2pdf if WeasyPrint is unavailable.
    """
    html_content = render_template(template_name, **context)

    if _WEASYPRINT_AVAILABLE:
        try:
            if base_url is None:
                base_url = current_app.root_path
            wp_doc = weasyprint.HTML(string=html_content, base_url=base_url)
            pdf_bytes = wp_doc.write_pdf()
            return pdf_bytes
        except Exception as e:
            logging.error(f"WeasyPrint PDF rendering failed: {e}. Attempting fallback to xhtml2pdf.")

    # Fallback to xhtml2pdf if WeasyPrint is not installed or threw an error
    from xhtml2pdf import pisa
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        html_content,
        dest=pdf_buffer,
        link_callback=lambda uri, rel: os.path.join(current_app.root_path, uri.lstrip('/'))
    )
    if pisa_status.err:
        raise RuntimeError("Failed to generate PDF with both WeasyPrint and xhtml2pdf")
    
    pdf_buffer.seek(0)
    return pdf_buffer.read()


def make_pdf_response(template_name: str, context: dict, filename: str = "prescription.pdf", download: bool = False):
    """
    Returns a Flask Response containing the rendered PDF.
    - download=False: 'inline' disposition (browser preview / view tab)
    - download=True: 'attachment' disposition (force browser file download)
    """
    pdf_data = generate_pdf_bytes(template_name, context)
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    disposition = 'attachment' if download else 'inline'
    response.headers['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response
