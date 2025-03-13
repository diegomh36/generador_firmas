import base64
from io import BytesIO
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Page, Content, Signature
from .forms import PageForm
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from reportlab.lib import colors
from datetime import datetime
import locale
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from PIL import Image
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import json
from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Page, Signature

class StaffRequiredMixin(object):
    """
    Este mixin requiere que el usuario sea miembro del staff
    """
    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super(StaffRequiredMixin, self).dispatch(request, *args, **kwargs)

locale.setlocale(locale.LC_TIME, 'es_ES')
# Create your views here.


class PageListView(ListView):
    model = Page


class PageDetailView(DetailView):
    model = Page


class PageCreate(CreateView):
    model = Page
    form_class = PageForm
    success_url = reverse_lazy('pages:pages')
    
@method_decorator(staff_member_required, name='dispatch')
class PageUpdate(UpdateView):
    model = Page
    form_class = PageForm
    template_name_suffix = '_update_form'
    success_url = reverse_lazy('pages:pages')

    def get_success_url(self):
        return reverse_lazy('pages:update', args=[self.object.id]) + '?ok'

@method_decorator(staff_member_required, name='dispatch')
class PageDelete(DeleteView):
    model = Page
    success_url = reverse_lazy('pages:pages')

def firmar_documento(request, page_id):
    page = get_object_or_404(Page, id=page_id)

    if request.method == "POST":
        signer_name = request.POST.get("signer_name")
        signature_image = request.POST.get("signature_image")  # Base64 de la firma

        # Guardar la firma en la base de datos
        Signature.objects.create(page=page, signer_name=signer_name, signature_image=signature_image)

        # Generar un nuevo PDF con firmas (sobreescribir)
        return redirect("descargar_pdf", page_id=page.id)  # Regenerar el PDF firmado

    return render(request, "pages/firmar_documento.html", {"page": page})

def enviar_pdf(request, page_id):
    page = get_object_or_404(Page, id=page_id)

    # Ruta del archivo en la carpeta static
    pdf_filename = f"formacion_{page.id}.pdf"
    pdf_path = os.path.join(settings.BASE_DIR, "pages/static/pages/pdfs/", pdf_filename)

    # Configurar el correo
    subject = f"Formación de {page.name}"
    message = f"Adjunto encontrarás el PDF de la formación de {page.name}."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ["diegodamanrique@gmail.com"]

    email = EmailMessage(subject, message, from_email, recipient_list)

    # Adjuntar PDF si existe
    if os.path.exists(pdf_path):
        email.attach_file(pdf_path)
        email.send()
          # Redirigir a una vista de confirmación
        return JsonResponse({"success": True, "message": "Correo enviado correctamente."})
      # Redirigir si el archivo no existe
    else:
        return JsonResponse({"success": False, "message": "Envío fallido."})

@require_POST
def enviar_pdf_email(request, page_id):
    try:
        # Obtener los datos del request
        data = json.loads(request.body)
        email_destinatario = data.get('email_destinatario')
        
        # Correo predeterminado 
        email_predeterminado = "diegodmh22@gmail.com"  
        
        # Obtener la página y generar el PDF
        page = Page.objects.get(id=page_id)
        pdf_filename = f"formacion_{page.id}.pdf"
        pdf_path = os.path.join(settings.BASE_DIR, "pages/static/pages/pdfs/", pdf_filename)
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
        
        # Crear el correo electrónico
        subject = f"Parte de formación - {page.title}"
        body = f"Adjunto encontrarás el parte de formación llevado a cabo el día {page.date}."
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email='diegodmh22@gmail.com',  # Usa el remitente predeterminado configurado en settings.py
            to=[email_destinatario, email_predeterminado]
        )
        
        # Adjuntar el PDF
        email.attach(pdf_filename, pdf_content, 'application/pdf')
        
        # Enviar el correo
        email.send(fail_silently=False)
        
        return JsonResponse({"success": True})
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

def create_training(request):
    if request.method == "POST":
        form = PageForm(request.POST)
        if form.is_valid():
            page = form.save()
            sign_all = form.cleaned_data["sign_all"]
            return redirect("pages:firmar", page_id=page.id, sign_all=sign_all)  
    else:
        form = PageForm()
    return render(request, "pages/create_training.html", {"form": form})

def finalizar_view(request, page_id):
    page = get_object_or_404(Page, id=page_id)
    return render(request, "pages/final_page.html", {"page": page})


def sign_training(request, page_id, sign_all):
    print(f"Entrando a sign_training - page_id: {page_id}, sign_all: {sign_all}")
    page = get_object_or_404(Page, id=page_id)
    signed_count = Signature.objects.filter(page=page).count()
    print(f"Firmas actuales: {signed_count}, requeridas: {page.assistants}")

    if request.method == "POST":
        print("Entró al bloque POST")
        signer_name = request.POST["signer_name"]
        signature_data = request.POST["signature"]

        # Verifica que la firma tenga datos antes de guardar
        if not signature_data or signature_data == "data:,":
            print("la firma no tiene datos")
            return render(request, "pages/sign_training.html", {
                "page": page,
                "signed_count": signed_count,
                "error": "La firma no puede estar vacía."
            })

        # Crear la firma
        Signature.objects.create(page=page, signer_name=signer_name, signature_image=signature_data)

        # Recalcular el número de firmas después de crear la nueva
        updated_signed_count = Signature.objects.filter(page=page).count()

        # Si es "all" y todavía faltan firmas, vuelve a la página de firma
        if sign_all == "all" and updated_signed_count < page.assistants:
            print(f"Faltan firmas")
            return redirect("pages:firmar", page_id=page.id, sign_all=sign_all)

        # En cualquier otro caso (ya sea porque se completaron todas las firmas o no es "all"), finaliza
        generate_pdf(request, page.id)
        return redirect("pages:finalizar", page_id=page.id)

    # Si todos ya firmaron y estamos en modo "all", ir directamente a finalizar
    if sign_all == "all" and signed_count >= page.assistants:
        generate_pdf(request, page.id)
        return redirect("pages:finalizar", page_id=page.id)

    print(f"No estoy entrando al if")
    return render(request, "pages/sign_training.html", {"page": page, "signed_count": signed_count})

def sign_training2(request, page_id, sign_all):
    print(f"Entrando a sign_training - page_id: {page_id}, sign_all: {sign_all}")
    page = get_object_or_404(Page, id=page_id)
    signed_count = Signature.objects.filter(page=page).count()
    print(f"Firmas actuales: {signed_count}, requeridas: {page.assistants}")

    if request.method == "POST":
        print("Entró al bloque POST")
        signer_name = request.POST["signer_name"]
        signature_data = request.POST["signature"]

        # Verifica que la firma tenga datos antes de guardar
        if not signature_data or signature_data == "data:,":
            print("la firma no tiene datos")
            return render(request, "pages/sign_training.html", {
                "page": page,
                "signed_count": signed_count,
                "error": "La firma no puede estar vacía."
            })

        # Crear la firma
        Signature.objects.create(page=page, signer_name=signer_name, signature_image=signature_data)

        # Recalcular el número de firmas después de crear la nueva
        updated_signed_count = Signature.objects.filter(page=page).count()

        # Si es "all" y todavía faltan firmas, vuelve a la página de firma
        if sign_all == "all" and updated_signed_count < page.assistants:
            print(f"Faltan firmas")
            return redirect("pages:firmar", page_id=page.id, sign_all=sign_all)

        # En cualquier otro caso (ya sea porque se completaron todas las firmas o no es "all"), finaliza
        generate_pdf(request, page.id)
        return redirect("pages:finalizar", page_id=page.id)

    # Si todos ya firmaron y estamos en modo "all", ir directamente a finalizar
    if sign_all == "all" and signed_count >= page.assistants:
        generate_pdf(request, page.id)
        return redirect("pages:finalizar", page_id=page.id)

    print(f"No estoy entrando al if")
    return render(request, "pages/sign_training2.html", {"page": page, "signed_count": signed_count})



def generate_pdf(request, page_id):
    page = get_object_or_404(Page, id=page_id)
    signatures = Signature.objects.filter(page=page)

    pdf_filename = f"formacion_{page.id}.pdf"
    pdf_path = os.path.join(settings.BASE_DIR, "pages/static/pages/pdfs/", pdf_filename)

     # Crear la carpeta si no existe
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    #Imagenes y estilos de fuentes
    ruta_logotipo = os.path.join(settings.BASE_DIR, "pages/static/pages/img/logotipo.png")
    ruta_correo = os.path.join(settings.BASE_DIR, "pages/static/pages/img/correo.PNG")
    ruta_movil = os.path.join(settings.BASE_DIR, "pages/static/pages/img/movil.PNG")
    ruta_world = os.path.join(settings.BASE_DIR, "pages/static/pages/img/world.PNG")
    pdfmetrics.registerFont(TTFont('Roboto-Regular', 'pages/static/pages/fonts/RobotoSlab-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Medium', 'pages/static/pages/fonts/RobotoSlab-Medium.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', 'pages/static/pages/fonts/RobotoSlab-Bold.ttf'))
    styles = getSampleStyleSheet()
    bold_style = styles["Normal"]
    bold_style.fontName = "Helvetica-Bold"

    estilo_texto = ParagraphStyle(
        'MiEstilo',
        parent=getSampleStyleSheet()['Normal'],
        textColor=colors.Color(0.3, 0.3, 0.3),
        fontSize=13
    )
    estilo_texto_footer = ParagraphStyle(
        'MiEstilo',
        parent=getSampleStyleSheet()['Normal'],
        textColor=colors.Color(0.3, 0.3, 0.3),
        fontSize=11
    )

    # Variables de formato para el pdf
    Y = 760
    X = 50
    x_start = X
    y_start = Y
    y_footer = 30
    row_height = 55
    col_width = 250
    page_number = 1  
    max_rows_first_page = 5  
    max_rows_other_pages = 8

    def set_font_color():
        p.setFillColor(colors.Color(0.3, 0.3, 0.3))

    #Función para generar cabecera de la pagina
    def draw_header():
        nonlocal y_start
        p.setFillColor(colors.Color(0.1686, 0.1647, 0.1451))
        p.setFont("Roboto-Regular", 20)
        p.drawString(x_start, y_start, "   Visionary")
        p.setFont("Roboto-Bold", 20)
        p.drawString(x_start, y_start-20, "Hospitality")
        p.drawImage(ruta_logotipo, x_start+118, 730, width=52, height=50)
        y_start -= 88
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 20)
        p.drawString(x_start, y_start, "Hoja de formación")
        y_start -= 20
        set_font_color()

    # Función para generar cabecera de la tabla
    def draw_table_header():
        nonlocal y_start
        p.setFont("Helvetica-Bold", 12)
        y_start -= 20
        p.setStrokeColor(colors.black)
        p.line(x_start, y_start + 12, x_start + col_width * 2, y_start + 12)
        width_col = 50
        for i in range(3):
            p.line(width_col, y_start + 12, width_col, y_start - 8)
            width_col += col_width
        p.drawString(x_start+10, y_start, "Nombre")
        p.drawString(x_start + col_width +10, y_start, "Firma")
        p.line(x_start, y_start -8, x_start + col_width * 2, y_start -8)

    #Función para generar pie de la pagina
    def draw_footer():
        nonlocal y_start
        nonlocal x_start
        set_font_color()
        y_start -= 30
        p.drawString(x_start, y_start, "Formador/a:")
        y_start -= 23
        p.setFont("Helvetica", 13)
        p.drawString(x_start, y_start, f"{page.name}")

        y_start -= 50
        if page.date:
            fecha =  page.date
            dia = fecha.day
            mes = fecha.strftime("%B")
            anyo = fecha.year
            

            p_text = Paragraph(f"Fecha <b>{dia}</b> de <b>{mes}</b> de <b>{anyo}</b>", estilo_texto)
            p_text.wrapOn(p, 400, 20)
            p_text.drawOn(p, x_start, y_start)
        else:
            p.drawString(x_start, y_start, "Sin fecha seleccionada")

        p.setFont("Helvetica", 11)
        p.drawString(510, y_footer, f"{page_number}")

        # Iconos de contacto del footer
        p.drawImage(ruta_movil, x_start, y_footer - 5, width=20, height=20)
        x_start += 22
        p_text = Paragraph(f"(+34) <b>686 942 148</b>", estilo_texto_footer)
        p_text.wrapOn(p, 400, 20)
        p_text.drawOn(p, x_start, y_footer)
        x_start += 115
        p.drawImage(ruta_correo, x_start, y_footer - 5, width=20, height=20)
        x_start += 22
        p_text = Paragraph(f"<b>info@visionaryh.com</b>", estilo_texto_footer)
        p_text.wrapOn(p, 400, 20)
        p_text.drawOn(p, x_start, y_footer)
        x_start += 135
        p.drawImage(ruta_world, x_start, y_footer - 5, width=20, height=20)
        x_start += 22
        p_text = Paragraph(f"<b>visionaryh.com</b>", estilo_texto_footer)
        p_text.wrapOn(p, 400, 20)
        p_text.drawOn(p, x_start, y_footer)
    
    # Primera página con título y checkboxes
    draw_header()
    p.setFont("Helvetica", 11)
    p.drawString(x_start, y_start, "Una vez realizada la instalación, te damos la bienvenida a la suite de herramientas de Visionary.")
    y_start -= 15
    p.drawString(x_start, y_start, "Para su correcto uso procedemos a la formación y explicación de los siguientes contenidos:")

    # Dibujar checkboxes con contenidos
    y_start -= 45
    for content in page.contents.all():
            p.setStrokeColor(colors.grey)
            p.setFillColor(colors.white)
            p.rect(x_start, y_start-1, 10, 10, stroke=1, fill=1) 
            set_font_color()
            p.drawString(x_start + 20, y_start, f"{content.name}")
            y_start -= 20

    y_start -= 40
    p.drawString(x_start, y_start, "Asistentes:")

    draw_table_header()

    rows_on_page = 0
    max_rows_current_page = max_rows_first_page  

    # Procesar cada firma
    for signature in signatures:
        # Comprobar si necesitamos una nueva página
        if rows_on_page >= max_rows_current_page:
            draw_footer()
            p.showPage()
            page_number += 1
            
            # Configuración para la nueva página
            max_rows_current_page = max_rows_other_pages
            y_start = Y  
            x_start = X
            draw_header()
            draw_table_header()
            rows_on_page = 0   
        
        # Dibujar el nombre en la primera columna
        p.drawString(x_start + 10, y_start - row_height/2, signature.signer_name)
        
        # Dibujar la firma en la segunda columna
        try:
            # Procesar la imagen de la firma
            signature_data = signature.signature_image
            if "," in signature_data:
                signature_data = signature_data.split(",")[1]
            
            img_data = base64.b64decode(signature_data)
            img = Image.open(BytesIO(img_data))
            
            # Crear fondo blanco
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            
            # Combinar firma con fondo
            if img.mode == "RGBA":
                background.paste(img, (0, 0), img)
            else:
                background.paste(img, (0, 0))
            
            background = background.convert("RGB")
            
            # Guardar en buffer
            img_buffer = BytesIO()
            background.save(img_buffer, format="JPEG", quality=95)
            img_buffer.seek(0)
            
            # Dimensiones de la imagen
            img_width = 200
            img_height = 40  
            
            # Colocar la firma en la segunda columna
            
            img_reader = ImageReader(img_buffer)
            p.drawImage(
                img_reader, 
                x_start + col_width + 25,  
                y_start - row_height + 5,  
                width=img_width, 
                height=img_height, 
                mask='auto'
            )
            
        except Exception as e:
            p.drawString(x_start + col_width + 10, y_start - row_height/2, f"Error: {str(e)}")
        
        # Dibujar las líneas de la fila
        p.line(x_start, y_start - row_height, x_start + col_width * 2, y_start - row_height)  # Línea inferior
        p.line(x_start, y_start, x_start, y_start - row_height)  # Línea izquierda
        p.line(x_start + col_width, y_start, x_start + col_width, y_start - row_height)  # Línea central
        p.line(x_start + col_width * 2, y_start, x_start + col_width * 2, y_start - row_height)  # Línea derecha
        
        # Actualizar posición para la siguiente fila
        y_start -= row_height
        rows_on_page += 1

    draw_footer()
    p.showPage()

    p.save()
    buffer.seek(0)

    # Guardar el PDF en la carpeta especificada
    with open(pdf_path, "wb") as f:
        f.write(buffer.read())

    # Construir la URL del PDF basado en static
    pdf_url = f"/static/pages/pdfs/{pdf_filename}"

    
    return JsonResponse({"success": True, "pdf_url": pdf_url})



    
def generar_pdf(request):
    if request.method == "POST":
        form = PageForm(request.POST)

        # Si en el formulario no se marcaron los checkboxes, mostrar emensaje de error
        if not form.is_valid():
            return render(request, "pages/page_form.html", {"form": form, "error": "Debe seleccionar al menos un contenido."})
        
        name = request.POST.get('name', '')
        assistants = int(request.POST.get('assistants', 1))
        date = request.POST.get('date', '')
        content_ids = request.POST.getlist('contents')  
        selected_contents = Content.objects.filter(id__in=content_ids)

        ruta_logotipo = os.path.join(settings.BASE_DIR, "pages\static\pages\img\logotipo.png")
        ruta_correo = os.path.join(settings.BASE_DIR, "pages\static\pages\img\correo.PNG")
        ruta_movil = os.path.join(settings.BASE_DIR, "pages\static\pages\img\movil.PNG")
        ruta_world = os.path.join(settings.BASE_DIR, "pages\static\pages\img\world.PNG")
        pdfmetrics.registerFont(TTFont('Roboto-Regular', 'pages/static/pages/fonts/RobotoSlab-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Roboto-Medium', 'pages/static/pages/fonts/RobotoSlab-Medium.ttf'))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', 'pages/static/pages/fonts/RobotoSlab-Bold.ttf'))

        styles = getSampleStyleSheet()
        bold_style = styles["Normal"]
        bold_style.fontName = "Helvetica-Bold"

        estilo_texto = ParagraphStyle(
            'MiEstilo',
            parent=getSampleStyleSheet()['Normal'],
            textColor=colors.Color(0.3, 0.3, 0.3),
            fontSize=13
        )
        estilo_texto_footer = ParagraphStyle(
            'MiEstilo',
            parent=getSampleStyleSheet()['Normal'],
            textColor=colors.Color(0.3, 0.3, 0.3),
            fontSize=11
        )

        
        response = HttpResponse(content_type='application/pdf')

        if "generar" in request.POST:
            response['Content-Disposition'] = 'attachment; filename="documento.pdf"'
        else:
            response['Content-Disposition'] = 'inline; filename="documento.pdf"'

        p = canvas.Canvas(response)

        # Variables de formato para el pdf
        x_start = 50
        y_start = 760
        y_footer = 30
        row_height = 55
        col_width = 250
        page_number = 1  
        max_rows_first_page = 5  
        max_rows_other_pages = 8 

        def set_font_color():
            p.setFillColor(colors.Color(0.3, 0.3, 0.3))

        def draw_header():
            nonlocal y_start
            p.setFillColor(colors.Color(0.1686, 0.1647, 0.1451))
            p.setFont("Roboto-Regular", 20)
            p.drawString(x_start, y_start, "   Visionary")
            p.setFont("Roboto-Bold", 20)
            p.drawString(x_start, y_start-20, "Hospitality")
            p.drawImage(ruta_logotipo, x_start+118, 730, width=52, height=50)
            y_start -= 88
            p.setFillColor(colors.black)
            p.setFont("Helvetica-Bold", 20)
            p.drawString(x_start, y_start, "Hoja de formación")
            y_start -= 20
            set_font_color()

        def draw_footer():
            nonlocal y_start
            nonlocal x_start
            set_font_color()
            p.drawString(x_start, y_start, "Formador/a:")
            y_start -= 23
            p.setFont("Helvetica", 13)
            p.drawString(x_start, y_start, f"{name}")

            y_start -= 50
            if date:
                fecha =  datetime.strptime(date, "%Y-%m-%d")
                dia = fecha.day
                mes = fecha.strftime("%B")
                anyo = fecha.year
                

                p_text = Paragraph(f"Fecha <b>{dia}</b> de <b>{mes}</b> de <b>{anyo}</b>", estilo_texto)
                p_text.wrapOn(p, 400, 20)
                p_text.drawOn(p, x_start, y_start)
            else:
                p.drawString(x_start, y_start, "Sin fecha seleccionada")

            p.setFont("Helvetica", 11)
            p.drawString(510, y_footer, f"{page_number}")

            # Iconos de contacto del footer
            p.drawImage(ruta_movil, x_start, y_footer - 5, width=20, height=20)
            x_start += 22
            p_text = Paragraph(f"(+34) <b>686 942 148</b>", estilo_texto_footer)
            p_text.wrapOn(p, 400, 20)
            p_text.drawOn(p, x_start, y_footer)
            x_start += 115
            p.drawImage(ruta_correo, x_start, y_footer - 5, width=20, height=20)
            x_start += 22
            p_text = Paragraph(f"<b>info@visionaryh.com</b>", estilo_texto_footer)
            p_text.wrapOn(p, 400, 20)
            p_text.drawOn(p, x_start, y_footer)
            x_start += 135
            p.drawImage(ruta_world, x_start, y_footer - 5, width=20, height=20)
            x_start += 22
            p_text = Paragraph(f"<b>visionaryh.com</b>", estilo_texto_footer)
            p_text.wrapOn(p, 400, 20)
            p_text.drawOn(p, x_start, y_footer)


        # Primera página con título y checkboxes
        draw_header()
        p.setFont("Helvetica", 11)
        p.drawString(x_start, y_start, "Una vez realizada la instalación, te damos la bienvenida a la suite de herramientas de Visionary.")
        y_start -= 15
        p.drawString(x_start, y_start, "Para su correcto uso procedemos a la formación y explicación de los siguientes contenidos:")
        
        # Dibujar checkboxes con contenidos
        y_start -= 45
        for content in selected_contents:
            p.setStrokeColor(colors.grey)
            p.setFillColor(colors.white)
            p.rect(x_start, y_start-1, 10, 10, stroke=1, fill=1) 
            set_font_color()
            p.drawString(x_start + 20, y_start, f"{content.name}")
            y_start -= 20

        y_start -= 40
        p.drawString(x_start, y_start, "Asistentes:")

        # Cabecera de la tabla
        def draw_table_header():
            nonlocal y_start
            p.setFont("Helvetica-Bold", 12)
            y_start -= 20
            p.setStrokeColor(colors.black)
            p.line(x_start, y_start + 12, x_start + col_width * 2, y_start + 12)
            x_start_col = 50
            for i in range(3):
                p.line(x_start_col, y_start + 12, x_start_col, y_start - 8)
                x_start_col += col_width    
            p.drawString(x_start+10, y_start, "Nombre")
            p.drawString(x_start + col_width +10, y_start, "Firma")
            p.line(x_start, y_start -8, x_start + col_width * 2, y_start -8)
            y_start -= row_height

        draw_table_header()

        rows_on_page = 0
        max_rows_current_page = max_rows_first_page  

        # Dibujar filas de la tabla y manejar paginación
        for i in range(assistants):
            if rows_on_page >= max_rows_current_page:
                draw_footer()  
                p.showPage()
                page_number += 1

                # Configuración para la nueva página y reinicio de altura inicial
                max_rows_current_page = max_rows_other_pages  
                y_start = 760 
                x_start = 50 
                draw_header()
                draw_table_header()
                rows_on_page = 0

            # Dibujar filas según numero de asistentes
            p.line(x_start, y_start, x_start + col_width * 2, y_start)
            x_start_col = 50
            for j in range(3):
                p.line(x_start_col, y_start + row_height, x_start_col, y_start)
                x_start_col += col_width 
            y_start -= row_height
            rows_on_page += 1

        draw_footer()
        p.showPage()
        p.save()
        return response
