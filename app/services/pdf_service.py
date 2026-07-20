import io
import hmac
import hashlib
import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from app.core.config import settings

def generate_signature(student_id: str, paper_id: int, cert_id: str) -> str:
    """
    Generates a SHA-256 HMAC cryptographic signature for a certificate.
    """
    payload = f"{student_id}:{paper_id}:{cert_id}"
    return hmac.new(
        settings.PDF_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def verify_signature(student_id: str, paper_id: int, cert_id: str, signature: str) -> bool:
    """
    Verifies the certificate's cryptographic signature.
    """
    expected = generate_signature(student_id, paper_id, cert_id)
    return hmac.compare_digest(expected, signature)

class NumberedCanvas(canvas.Canvas):
    """
    Canvas to handle professional page numbers and running headers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Draw header (skip first page)
        if self._pageNumber > 1:
            self.drawString(54, 750, "AI Exam & Evaluation Platform — Marksheet")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 742, letter[0] - 54, 742)

        # Draw footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 40, page_text)
        self.drawString(54, 40, "Confidential — Automated AI Assessment Result")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 52, letter[0] - 54, 52)
        
        self.restoreState()

def generate_marksheet_pdf(submission, paper, questions, student_name: str = None, father_name: str = None) -> bytes:
    """
    Generates a structured Marksheet PDF containing score breakdowns and explanations.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=15
    )
    
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2C5282"),
        spaceBefore=15,
        spaceAfter=10
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#4A5568")
    )
    
    meta_val_style = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#1A202C")
    )

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#2D3748")
    )

    cell_bold_style = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1A202C")
    )

    story = []

    # Title
    story.append(Paragraph("EXAM PERFORMANCE MARKSHEET", title_style))
    story.append(Spacer(1, 10))

    # Meta Info Box
    issue_date = submission.created_at.strftime("%Y-%m-%d %H:%M:%S") if submission.created_at else datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    meta_data = [
        [Paragraph("Candidate Name:", meta_label_style), Paragraph(student_name or submission.student_id, meta_val_style),
         Paragraph("Father's Name:", meta_label_style), Paragraph(father_name or "N/A", meta_val_style)],
        [Paragraph("Candidate ID:", meta_label_style), Paragraph(submission.student_id, meta_val_style),
         Paragraph("Paper Code:", meta_label_style), Paragraph(paper.code, meta_val_style)],
        [Paragraph("Paper Title:", meta_label_style), Paragraph(paper.title, meta_val_style),
         Paragraph("Submission Date:", meta_label_style), Paragraph(issue_date, meta_val_style)],
        [Paragraph("Overall Score:", meta_label_style), Paragraph(f"{submission.overall_score:.2f} / {paper.total_marks:.2f}", meta_val_style),
         Paragraph("Grade / Percentage:", meta_label_style), Paragraph(f"{submission.final_grade} ({submission.percentage:.2f}%)", meta_val_style)]
    ]
    
    meta_table = Table(meta_data, colWidths=[1.3*inch, 2.2*inch, 1.3*inch, 2.2*inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Detailed Question Breakdown
    story.append(Paragraph("Question-by-Question Score Breakdown", section_style))
    
    # Table headers
    headers = [
        Paragraph("<b>Q.No</b>", cell_bold_style),
        Paragraph("<b>Type</b>", cell_bold_style),
        Paragraph("<b>Max Marks</b>", cell_bold_style),
        Paragraph("<b>Score</b>", cell_bold_style),
        Paragraph("<b>Evaluation & Rationale</b>", cell_bold_style)
    ]
    
    breakdown_data = [headers]
    
    # Map questions for fast lookup
    q_map = {q.id: q for q in questions}
    evals = submission.evaluated_responses or []
    
    for idx, ev in enumerate(evals, 1):
        q_id = ev.get("question_id")
        q = q_map.get(q_id)
        q_type = q.type.capitalize() if q else "N/A"
        max_m = q.marks if q else 0.0
        score = ev.get("score", 0.0)
        feedback = ev.get("rationale", "No explanation provided.")
        
        row = [
            Paragraph(str(idx), cell_style),
            Paragraph(q_type, cell_style),
            Paragraph(f"{max_m:.1f}", cell_style),
            Paragraph(f"{score:.1f}", cell_style),
            Paragraph(feedback, cell_style)
        ]
        breakdown_data.append(row)
        
    breakdown_table = Table(breakdown_data, colWidths=[0.5*inch, 0.9*inch, 0.9*inch, 0.9*inch, 3.8*inch])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(breakdown_table)
    
    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()

def generate_certificate_pdf(certificate, student_name: str, paper_title: str, grade: str, father_name: str = None) -> bytes:
    """
    Generates a Certificate of Completion in Landscape orientation, featuring a border and signature.
    """
    buffer = io.BytesIO()
    
    # Landscape Letter
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom Certificate styles
    cert_title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=38,
        alignment=1, # Center
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=15
    )

    cert_sub_style = ParagraphStyle(
        "CertSub",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=16,
        leading=20,
        alignment=1, # Center
        textColor=colors.HexColor("#718096"),
        spaceAfter=20
    )

    cert_name_style = ParagraphStyle(
        "CertName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        alignment=1, # Center
        textColor=colors.HexColor("#2B6CB0"),
        spaceAfter=15
    )

    cert_body_style = ParagraphStyle(
        "CertBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=14,
        leading=20,
        alignment=1, # Center
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=30
    )

    cert_meta_style = ParagraphStyle(
        "CertMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#4A5568")
    )

    cert_sig_style = ParagraphStyle(
        "CertSig",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#718096")
    )

    def draw_background(canvas, doc):
        canvas.saveState()
        # Draw elegant double border
        canvas.setStrokeColor(colors.HexColor("#1A365D"))
        canvas.setLineWidth(4)
        canvas.rect(20, 20, landscape(letter)[0] - 40, landscape(letter)[1] - 40)
        
        canvas.setStrokeColor(colors.HexColor("#D69E2E"))
        canvas.setLineWidth(1.5)
        canvas.rect(26, 26, landscape(letter)[0] - 52, landscape(letter)[1] - 52)
        
        # Add decorative corner elements
        width = landscape(letter)[0]
        height = landscape(letter)[1]
        canvas.setFillColor(colors.HexColor("#1A365D"))
        canvas.circle(35, 35, 6, fill=True, stroke=False)
        canvas.circle(width - 35, 35, 6, fill=True, stroke=False)
        canvas.circle(35, height - 35, 6, fill=True, stroke=False)
        canvas.circle(width - 35, height - 35, 6, fill=True, stroke=False)
        
        canvas.restoreState()

    story = []
    story.append(Spacer(1, 40))
    story.append(Paragraph("CERTIFICATE OF EXCELLENCE", cert_title_style))
    story.append(Paragraph("This certificate is proudly presented to", cert_sub_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(student_name.upper(), cert_name_style))
    if father_name and father_name != "N/A":
        story.append(Paragraph(f"S/O Shri {father_name}", cert_sub_style))
        story.append(Spacer(1, 10))
    else:
        story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"for outstanding performance and successful completion of the automated AI examination for<br/>"
        f"<b>{paper_title}</b> with a final grade of <b>{grade}</b>.", 
        cert_body_style
    ))
    story.append(Spacer(1, 20))

    # Add Signatures
    sig_data = [
        [
            Paragraph("____________________________<br/>AI Evaluation System", cert_meta_style),
            Paragraph(f"<b>Issue Date</b><br/>{certificate.issue_date.strftime('%Y-%m-%d')}", cert_meta_style),
            Paragraph("____________________________<br/>Registrar, Academic Board", cert_meta_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 45))

    # Digital Signature Box
    story.append(Paragraph(f"Certificate ID: {certificate.id}", cert_meta_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"SHA-256 Verification Hash: {certificate.digital_signature}", cert_sig_style))

    doc.build(story, onFirstPage=draw_background)
    buffer.seek(0)
    return buffer.getvalue()
