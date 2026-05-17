import io

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from marketplace.models import Transaction


@login_required
def index(request):
    user = request.user
    transactions = (
        Transaction.objects
        .filter(Q(buyer=user) | Q(seller=user) | Q(user=user))
        .select_related('from_currency', 'to_currency', 'buyer', 'seller')
        .order_by('-created_at')
    )
    return render(request, 'transactions/index.html', {'transactions': transactions})


@login_required
def export_pdf(request, txn_id):
    user = request.user
    try:
        txn = Transaction.objects.select_related(
            'from_currency', 'to_currency', 'buyer', 'seller', 'user', 'deal'
        ).get(pk=txn_id)
    except Transaction.DoesNotExist:
        raise Http404

    if txn.buyer != user and txn.seller != user and txn.user != user:
        raise Http404

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    orange    = colors.HexColor('#ff9500')
    dark      = colors.HexColor('#1a2535')
    muted     = colors.HexColor('#6b7a8d')
    row_alt   = colors.HexColor('#f7f9fb')
    white     = colors.white

    title_style = ParagraphStyle('title', fontSize=18, textColor=dark,   fontName='Helvetica-Bold', spaceAfter=2)
    sub_style   = ParagraphStyle('sub',   fontSize=9,  textColor=muted,  fontName='Helvetica')
    label_style = ParagraphStyle('label', fontSize=9,  textColor=dark,  fontName='Helvetica-Bold', spaceBefore=4)
    value_style = ParagraphStyle('value', fontSize=9, textColor=dark,   fontName='Helvetica')

    counterparty = None
    if txn.type == 'exchange':
        counterparty = txn.seller if txn.buyer == user else txn.buyer

    def row(label, value):
        return [Paragraph(label, label_style), Paragraph(str(value) if value else '—', value_style)]

    story = [
        Paragraph('P2PTRADE', ParagraphStyle('logo', fontSize=13, textColor=orange, fontName='Helvetica-Bold')),
        Spacer(1, 3*mm),
        Paragraph('Transaction Reference', title_style),
        Spacer(1, 5*mm),
        Paragraph(f'Generated on {timezone.now().strftime("%d %b %Y, %H:%M")}', sub_style),
        Spacer(1, 5*mm),
        HRFlowable(width='100%', thickness=0.5, color=orange),
        Spacer(1, 5*mm),
    ]

    details = [
        row('Transaction ID',    f'#{txn.id}'),
        row('Payment Reference', txn.payment_reference or '—'),
        row('Type',              txn.type.capitalize()),
        row('Status',            txn.status.capitalize()),
        row('Currency Pair',     f'{txn.from_currency.code} → {txn.to_currency.code}'),
        row('Amount',            f'{txn.amount} {txn.from_currency.code}'),
        row('Received Amount',   f'{txn.received_amount} {txn.to_currency.code}' if txn.received_amount else '—'),
        row('Exchange Rate',     str(txn.rate)),
        row('Created At',        txn.created_at.strftime('%d %b %Y, %H:%M') if txn.created_at else '—'),
        row('Completed At',      txn.completed_at.strftime('%d %b %Y, %H:%M') if txn.completed_at else '—'),
    ]

    if counterparty:
        details += [
            row('Counterparty ID',    f'#{counterparty.id}'),
            row('Counterparty Email', counterparty.email),
            row('Counterparty Name',  counterparty.name or '—'),
        ]

    table = Table(details, colWidths=[55*mm, 110*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), white),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [white, row_alt]),
        ('TEXTCOLOR',     (0, 0), (-1, -1), dark),
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEBELOW',     (0, 0), (-1, -2), 0.3, colors.HexColor('#1a2535')),
    ]))

    story.append(table)
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=orange))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('This is an auto-generated receipt from P2PTrade.', sub_style))

    doc.build(story)
    buffer.seek(0)
    filename = f'txn_{txn.id}_{txn.payment_reference or "receipt"}.pdf'
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def admin_index(request):
    transactions = Transaction.objects.select_related(
        'buyer', 'seller', 'user', 'from_currency', 'to_currency'
    ).order_by('-created_at')
    return render(request, 'admin/transactions/admin_transaction.html', {'transactions': transactions})
