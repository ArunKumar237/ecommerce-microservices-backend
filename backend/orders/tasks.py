from celery import shared_task
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.utils import timezone
from io import BytesIO

from .models import Order


@shared_task
def send_order_confirmation_email(order_id: int):
    order = Order.objects.get(id=order_id)
    subject = f"Order #{order.id} confirmed"
    body = f"Hi {order.user.username},\n\nYour order #{order.id} has been paid successfully."
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [order.user.email])
    return f"Order confirmation sent to {order.user.email}"


@shared_task
def send_order_status_update_email(order_id: int, status: str):
    order = Order.objects.get(id=order_id)
    subject = f"Order #{order.id} status updated: {status}"
    body = f"Hi {order.user.username},\n\nYour order #{order.id} is now '{status}'."
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [order.user.email])
    return f"Status email sent ({order.id} -> {status})"


@shared_task
def generate_and_email_invoice(order_id: int):
    """
    Simple PDF invoice generator (you can improve layout later).
    Requires `reportlab` in requirements.txt
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    order = Order.objects.get(id=order_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    text = p.beginText(50, 800)

    text.textLine(f"Invoice for Order #{order.id}")
    text.textLine("")
    text.textLine(f"Customer: {order.user.username}")
    text.textLine(f"Email: {order.user.email}")
    text.textLine(f"Total Amount: {order.total_amount}")
    text.textLine(f"Status: {order.status}")
    text.textLine(f"Paid At: {order.paid_at}")
    text.textLine("")
    text.textLine("Items:")

    for item in order.items.all():
        text.textLine(f"- {item.product.name} x {item.quantity} @ {item.price_at_purchase}")

    p.drawText(text)
    p.showPage()
    p.save()

    buffer.seek(0)
    email = EmailMessage(
        subject=f"Invoice for Order #{order.id}",
        body="Please find attached your invoice.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email],
    )
    email.attach(f"invoice_order_{order.id}.pdf", buffer.read(), "application/pdf")
    email.send()
    return f"Invoice emailed to {order.user.email}"


@shared_task
def auto_cancel_unpaid_orders():
    """
    Cancel orders that remain 'pending' for more than 30 minutes.
    """
    cutoff = timezone.now() - timezone.timedelta(minutes=30)
    qs = Order.objects.filter(status="pending", created_at__lt=cutoff)
    count = qs.update(status="cancelled")
    return f"Auto-cancelled {count} unpaid orders"
