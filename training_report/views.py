import base64, re
from io import BytesIO
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import TrainingReport, Content, Signature
from .forms import TrainingReportForm, ImagenForm, VerificationForm, ImageVerificationForm
from reportlab.pdfgen import canvas
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
import os, io
from django.shortcuts import render, redirect, get_object_or_404
import google.generativeai as genai
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
from .models import TrainingReport, Signature
from .utils import *
from django.views import View

class StaffRequiredMixin(object):
    """
    Este mixin requiere que el usuario sea miembro del staff
    """
    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super(StaffRequiredMixin, self).dispatch(request, *args, **kwargs)

locale.setlocale(locale.LC_TIME, 'es_ES')
# Create your views here.


class TrainingReportListView(ListView):
    model = TrainingReport

class TrainingReportCreate(CreateView):
    model = TrainingReport
    form_class = TrainingReportForm
    success_url = reverse_lazy('training_report:training_report')

    def form_valid(self, form):
        training = form.save(commit=False)  # Guardar sin confirmar
        self.object = training
        training.save()  # Guardar la instancia de la página
        
        # Obtener los contenidos seleccionados y nuevos
        contents = self.request.POST.getlist('contents')
        
        content_objects = []
        for content_name in contents:
            content, created = Content.objects.get_or_create(name=content_name)  # Crea si no existe
            content_objects.append(content)

        # Asignar contenidos a la página
        training.contents.set(content_objects)

        return redirect(self.success_url)
    
@method_decorator(staff_member_required, name='dispatch')
class TrainingReportUpdate(UpdateView):
    model = TrainingReport
    form_class = TrainingReportForm
    template_name_suffix = '_update_form'
    success_url = reverse_lazy('training_report:training_report')

    def get_success_url(self):
        return reverse_lazy('training_report:update', args=[self.object.id]) + '?ok'

@method_decorator(staff_member_required, name='dispatch')
class TrainingReportDelete(DeleteView):
    model = TrainingReport
    success_url = reverse_lazy('training_report:training_report')


def send_email(request, training_id):
    try:
        # Verifica que la página exista
        training = TrainingReport.objects.get(id=training_id) 
        
        # Lee el cuerpo de la solicitud
        try:
            data = json.loads(request.body)
            email_destinatario = data.get('email_destinatario')
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "El cuerpo de la solicitud no es un JSON válido."})
        
        if not email_destinatario:
            return JsonResponse({"success": False, "error": "El campo 'email_destinatario' es requerido."})
        
        print(f"Email destinatario: {email_destinatario}")
        
        # Correo predeterminado
        email_predeterminado = "diegodmh22@gmail.com"
        
        # Ruta del PDF
        pdf_filename = f"formacion_{training.id}.pdf"
        pdf_path = os.path.join(settings.BASE_DIR, "training_report/static/training_report/pdfs/", pdf_filename)
        
        # Verifica que el PDF exista
        if not os.path.exists(pdf_path):
            return JsonResponse({"success": False, "error": f"El archivo PDF no existe en la ruta: {pdf_path}"})
        
        # Crear el correo electrónico
        subject = f"Parte de formación - {training.name}"
        body = f"Adjunto encontrarás el parte de formación llevado a cabo el día {training.date}."
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_destinatario, email_predeterminado]
        )
        
        # Adjuntar el PDF
        email.attach_file(pdf_path)
        
        # Enviar el correo
        email.send()
        
        return JsonResponse({"success": True})
        
    except TrainingReport.DoesNotExist:
        return JsonResponse({"success": False, "error": "La página no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

def create_training(request):
    if request.method == "POST":
        form = TrainingReportForm(request.POST)
        if form.is_valid():
            # Guardar la página primero sin hacer commit
            training = form.save(commit=False)
            training.save()
            
            # Procesar contenidos existentes
            existing_contents = form.cleaned_data.get('contents', [])
            for content in existing_contents:
                training.contents.add(content)
            
            # Procesar nuevos contenidos
            new_contents_text = form.cleaned_data.get('new_contents', '')
            if new_contents_text:
                new_content_titles = [title.strip() for title in new_contents_text.split(',') if title.strip()]
                for title in new_content_titles:
                    content = Content.objects.create(
                        name=title
                    )
                    training.contents.add(content)
            
            return redirect("training_report:sign_training", training_id=training.id)  
    else:
        form = TrainingReportForm()
    return render(request, "training_report/create_training.html", {"form": form})

def final_training_view(request, training_id):
    training = get_object_or_404(TrainingReport, id=training_id)
    return render(request, "training_report/final_training_report.html", {"training": training})


def sign_training(request, training_id):
    print(f"Entrando a sign_training - training_id: {training_id}")
    training = get_object_or_404(TrainingReport, id=training_id)
    signed_count = Signature.objects.filter(training=training).count()
    print(f"Firmas actuales: {signed_count}, requeridas: {training.assistants}")

    if request.method == "POST":
        print("Entró al bloque POST")
        signer_name = request.POST["signer_name"]
        signature_data = request.POST["signature"]

        # Verifica que la firma tenga datos antes de guardar
        if not signature_data or signature_data == "data:,":
            print("la firma no tiene datos")
            return render(request, "training_report/sign_training.html", {
                "training": training,
                "signed_count": signed_count,
                "error": "La firma no puede estar vacía."
            })

        # Crear la firma
        Signature.objects.create(training=training, signer_name=signer_name, signature_image=signature_data)

        # Recalcular el número de firmas después de crear la nueva
        updated_signed_count = Signature.objects.filter(training=training).count()

        # Si es "all" y todavía faltan firmas, vuelve a la página de firma
        if updated_signed_count < training.assistants:
            print(f"Faltan firmas")
            return redirect("training_report:sign_training", training_id=training.id)

        # En cualquier otro caso (ya sea porque se completaron todas las firmas o no es "all"), finaliza
        generate_pdf(request, training.id)
        return redirect("training_report:final_training", training_id=training.id)

    # Si todos ya firmaron y estamos en modo "all", ir directamente a finalizar
    if signed_count >= training.assistants:
        generate_pdf(request, training.id)
        return redirect("training_report:final_training", training_id=training.id)

    print(f"No estoy entrando al if")
    return render(request, "training_report/sign_training.html", {"training": training, "signed_count": signed_count})

def generate_pdf(request, training_id):
    training = get_object_or_404(TrainingReport, id=training_id)
    signatures = Signature.objects.filter(training=training)

    pdf_filename = f"formacion_{training.id}.pdf"
    pdf_path = os.path.join(settings.BASE_DIR, "training_report/static/training_report/pdfs/", pdf_filename)

     # Crear la carpeta si no existe
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    #Imagenes y estilos de fuentes
    ruta_logotipo = os.path.join(settings.BASE_DIR, "training_report/static/training_report/img/logotipo.png")
    ruta_correo = os.path.join(settings.BASE_DIR, "training_report/static/training_report/img/correo.PNG")
    ruta_movil = os.path.join(settings.BASE_DIR, "training_report/static/training_report/img/movil.PNG")
    ruta_world = os.path.join(settings.BASE_DIR, "training_report/static/training_report/img/world.PNG")
    pdfmetrics.registerFont(TTFont('Roboto-Regular', 'training_report/static/training_report/fonts/RobotoSlab-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Medium', 'training_report/static/training_report/fonts/RobotoSlab-Medium.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', 'training_report/static/training_report/fonts/RobotoSlab-Bold.ttf'))
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
    sign_all = training.sign_all
    first_sign_count = 0 
    first_signature = signatures[0]

    # Dimensiones de la imagen de firma
    img_width = 200
    img_height = 40

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
        p.line(x_start, y_start + 12, x_start + col_width * 2, y_start + 12) # Línea horizontal
        width_col = 50
        
        #Lineas verticales para cada firmante
        if sign_all == 'all':
            for i in range(3):
                p.drawString(x_start + col_width + 10, y_start, "Firma")
                p.line(width_col, y_start + 12, width_col, y_start - 8)
                width_col += col_width       
        #Lineas verticales para un firmante
        if sign_all == 'one': 
            for i in range(2):
                p.line(width_col, y_start + 12, width_col, y_start - 8)
                width_col += col_width * 2
        p.drawString(x_start+10, y_start, "Nombre")
        y_start -= 8   

    #Función para generar pie de la pagina
    def draw_footer():
        nonlocal y_start
        nonlocal x_start
        set_font_color()
        y_start -= 30
        p.drawString(x_start, y_start, "Formador/a:")
        if sign_all == 'one':
            # Obtener la primera firma de la lista
            if signatures:
                first_signature = signatures[0]
                signature_image = first_signature.signature_image

                # Procesar la imagen de la firma
                if "," in signature_image:
                    signature_image = signature_image.split(",")[1]

                img_data = base64.b64decode(signature_image)
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

                # Crear el ImageReader para reutilizarlo
                img_reader = ImageReader(img_buffer)
            else:
                print("La lista de firmas está vacía.")
                img_reader = None  # O maneja el caso de no haber firmas
            p.drawImage(
            img_reader,
            x_start + 240,
            y_start - 75,
            width=img_width,
            height=img_height,
            mask='auto'
            )
            p.drawString(x_start + 230, y_start, "Representante: ")
            p.setFont("Helvetica", 13)
            p.drawString(x_start + 230, y_start - 23, f"{first_signature.signer_name}")
        y_start -= 23
        p.setFont("Helvetica", 13)
        p.drawString(x_start, y_start, f"{training.name}")

        y_start -= 50
        if training.date:
            fecha =  training.date
            dia = fecha.day
            mes = fecha.strftime("%B")
            anyo = fecha.year
            hora = fecha.strftime("%H:%M")
            p_text = Paragraph(f"Fecha <b>{dia}</b> de <b>{mes}</b> de <b>{anyo}</b>", estilo_texto)
            p_text.wrapOn(p, 400, 20)
            p_text.drawOn(p, x_start, y_start)
            y_start -= 20
            p_text = Paragraph(f"Hora:  <b>{hora}</b>", estilo_texto)
            p_text.wrapOn(p, 400, 20)
            p_text.drawOn(p, x_start, y_start)
        else:
            p.drawString(x_start, y_start, "Sin fecha seleccionada")
        
        if sign_all == 'one':
            p.drawString(510, y_footer, f"{page_number}")


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
    for content in training.contents.all():
            p.setStrokeColor(colors.grey)
            p.setFillColor(colors.white)
            p.rect(x_start, y_start-1, 10, 10, stroke=1, fill=1) 
            set_font_color()
            p.drawString(x_start + 20, y_start, f"{content.name}")
            y_start -= 20

    y_start -= 45
    p.drawString(x_start + 5, y_start, "Asistentes:")

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
        
        # Dibujar el nombre en la primera columna si firman todos
        if sign_all == 'all' or first_sign_count >= 1:
            p.drawString(x_start + 10, y_start - row_height/2, signature.signer_name)

        
        
        # Dibujar la firma en la segunda columna
        try:
            # Procesar la imagen de la firma
            if sign_all == 'all': 
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
        
        
        
        if sign_all == 'all' or first_sign_count >= 1:
            p.line(x_start, y_start, x_start + col_width * 2, y_start) # Línea superior
            p.line(x_start, y_start - row_height, x_start + col_width * 2, y_start - row_height)  # Línea inferior
            if sign_all == 'all':
                p.line(x_start + col_width, y_start, x_start + col_width, y_start - row_height)  # Línea central vertical
            p.line(x_start + col_width * 2, y_start, x_start + col_width * 2, y_start - row_height)  # Línea derecha
            p.line(x_start, y_start, x_start, y_start - row_height)  # Línea izquierda
            
            y_start -= row_height

        first_sign_count += 1
        
        # Actualizar posición para la siguiente fila
        rows_on_page += 1

    draw_footer()
    p.showPage()

    p.save()
    buffer.seek(0)

    # Guardar el PDF en la carpeta especificada
    with open(pdf_path, "wb") as f:
        f.write(buffer.read())

    # Construir la URL del PDF basado en static
    pdf_url = f"/static/training_report/pdfs/{pdf_filename}"

    
    return JsonResponse({"success": True, "pdf_url": pdf_url})



#Para generar plantilla en blanco, de momento no lo estoy usando
# Si lo quiero añadir poner tambien la URL:
# path('generar-pdf/', generar_pdf, name='generar_pdf'),
def generar_pdf(request):
    if request.method == "POST":
        form = TrainingReportForm(request.POST)

        # Si en el formulario no se marcaron los checkboxes, mostrar emensaje de error
        if not form.is_valid():
            return render(request, "training_report/page_form.html", {"form": form, "error": "Debe seleccionar al menos un contenido."})
        
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

""" with open("token.config", "r") as token_file:
    api_key = token_file.read().strip()
    
genai.configure(api_key=api_key) """


genai.configure(api_key='AIzaSyCIzIx3jw-ikoLOcZXEzZreIZ134J34BGs')
model_vision = genai.GenerativeModel('gemini-2.0-flash')

def verificar_noticia(request):
    resultado = None
    if request.method == 'POST':
        form = VerificationForm(request.POST)
        if form.is_valid():
            titular = form.cleaned_data['titular']
            url = form.cleaned_data['url']
            texto_completo = form.cleaned_data['texto_completo']

            prompt = f"""Evalúa la fiabilidad de la siguiente información de manera aproximada proporcionada por el usuario. Considera los siguientes aspectos en tu análisis:

                    1.  Veracidad de las afirmaciones: ¿Son las afirmaciones fácticas precisas y están respaldadas por evidencia? Busca información en fuentes confiables para verificar los hechos mencionados.
                    2.  Credibilidad de la fuente (si se proporciona): Si se proporciona la URL o el nombre del medio, evalúa la reputación y el historial de la fuente en cuanto a precisión y posibles sesgos.
                    3.  Presencia de sesgos o intenciones: ¿Hay indicios de algún sesgo particular (político, ideológico, económico) o intento de manipulación en la forma en que se presenta la información?
                    4.  Calidad de la evidencia y el razonamiento: ¿Se presentan pruebas sólidas para respaldar las afirmaciones? ¿El razonamiento es lógico y coherente?
                    5.  Posible presencia de técnicas de desinformación: ¿Identificas el uso de alguna técnica común de desinformación (por ejemplo, apelación a la emoción, hombre de paja, falsa dicotomía, generalizaciones sin fundamento)?

                    Información proporcionada por el usuario:

                    * Titular/Fragmento: {titular}
                    * URL/Medio (Opcional): {url}
                    * Texto Completo (Opcional): {texto_completo}

                    Responde de la siguiente manera:

                    * Nivel de Fiabilidad: (Ejemplo: Alta, Moderada, Baja, No se puede determinar)
                    * Resumen de la Evaluación: Proporciona un breve resumen de tu análisis, destacando los puntos clave que respaldan tu evaluación del nivel de fiabilidad.
                    * Fuentes de Soporte (si las encuentras): Si encuentras fuentes confiables que verifiquen o desmientan la información, inclúyelas con un breve comentario sobre su relevancia.
                    * Posibles Sesgos o Técnicas de Desinformación Identificadas: Si identificas algún sesgo o técnica de desinformación, menciónalo y explica brevemente por qué lo consideras así.
                    * Advertencias o Consideraciones Adicionales: Incluye cualquier otra advertencia o consideración importante sobre la información analizada.

                    Consideraciones Adicionales para URLs:

                    * Si la URL proporcionada requiere una suscripción o pago para acceder al contenido completo, indica que el análisis se basará principalmente en el titular, la información pública disponible sobre el sitio y cualquier fragmento de texto proporcionado por el usuario o encontrado en otras fuentes.
                    * Prioriza el análisis del texto completo proporcionado por el usuario si está disponible, incluso si también se proporciona una URL de pago.
                    * Busca si la misma noticia o información está siendo reportada por otras fuentes de acceso público para complementar el análisis.
                    """

            try:
                # Get API key with fallbacks (environment var, direct configuration, or settings)
                api_key = os.environ.get('GOOGLE_API_KEY')
                
                if not api_key and hasattr(settings, 'GOOGLE_API_KEY'):
                    api_key = settings.GOOGLE_API_KEY
                
                # If no key found in environment or settings, use fallback key
                if not api_key:
                    api_key = 'YOUR_BACKUP_API_KEY'  # Replace with a valid API key
                    print("Warning: Using fallback API key")
                
                # Configure Gemini with the API key
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                respuesta_gemini = response.text
                
                # Parse the response into structured data
                nivel_fiabilidad = "No se pudo determinar"
                resumen_evaluacion = ""
                fuentes_soporte = []
                posibles_sesgos = ""
                advertencias = ""
                
                # Extract Nivel de Fiabilidad
                if "Nivel de Fiabilidad:" in respuesta_gemini:
                    nivel_parte = respuesta_gemini.split("Nivel de Fiabilidad:")[1].split("\n")[0].strip()
                    if nivel_parte:
                        nivel_fiabilidad = nivel_parte
                
                # Extract Resumen de la Evaluación
                if "Resumen de la Evaluación:" in respuesta_gemini:
                    partes = respuesta_gemini.split("Resumen de la Evaluación:")[1].split("\n")
                    for parte in partes:
                        if parte.strip() and not parte.strip().startswith("* ") and not parte.strip().startswith("Fuentes de Soporte:"):
                            resumen_evaluacion += parte.strip() + " "
                        if "Fuentes de Soporte:" in parte:
                            break
                
                # Extract Fuentes de Soporte
                if "Fuentes de Soporte:" in respuesta_gemini:
                    fuentes_parte = respuesta_gemini.split("Fuentes de Soporte:")[1]
                    if "Posibles Sesgos" in fuentes_parte:
                        fuentes_parte = fuentes_parte.split("Posibles Sesgos")[0]
                    
                    lineas = fuentes_parte.strip().split("\n")
                    for linea in lineas:
                        if linea.strip() and ":" not in linea and (linea.strip().startswith("-") or linea.strip().startswith("*")):
                            fuentes_soporte.append(linea.strip()[1:].strip())
                
                # Extract Posibles Sesgos
                if "Posibles Sesgos" in respuesta_gemini:
                    sesgos_parte = respuesta_gemini.split("Posibles Sesgos")[1]
                    if ":" in sesgos_parte:
                        sesgos_parte = sesgos_parte.split(":")[1]
                    if "Advertencias" in sesgos_parte:
                        sesgos_parte = sesgos_parte.split("Advertencias")[0]
                    posibles_sesgos = sesgos_parte.strip()
                
                # Extract Advertencias
                if "Advertencias" in respuesta_gemini:
                    advertencias_parte = respuesta_gemini.split("Advertencias")[1]
                    if ":" in advertencias_parte:
                        advertencias_parte = advertencias_parte.split(":")[1]
                    advertencias = advertencias_parte.strip()
                
                resultado = {
                    'nivel_fiabilidad': nivel_fiabilidad,
                    'resumen_evaluacion': resumen_evaluacion.strip(),
                    'fuentes_soporte': fuentes_soporte,
                    'posibles_sesgos': posibles_sesgos,
                    'advertencias': advertencias
                }
                
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                print(f"Error detallado al comunicarse con la API de Gemini: {e}")
                print(error_traceback)
                
                resultado = {
                    'error': f"Ocurrió un error al comunicarse con la API de Gemini: {e}",
                    'nivel_fiabilidad': "Error en la API",
                    'resumen_evaluacion': f"Error detallado: {str(e)}",
                    'advertencias': "Revisa la consola del servidor para más información."
                }
    else:
        form = VerificationForm()

    return render(request, 'training_report/analizar_imagen.html', {'form': form, 'resultado': resultado})

def parse_gemini_response(gemini_text_response):
    """
    Parsea la respuesta de texto de Gemini (esperando JSON)
    y devuelve un diccionario estructurado.
    """
    # Expresión regular para encontrar un bloque JSON, incluso si está dentro de ```json ... ```
    json_match = re.search(r'```json\s*(\{.*\})\s*```', gemini_text_response, re.DOTALL)
    if json_match:
        json_string = json_match.group(1)
    else:
        # Si no está en un bloque de código, intentamos buscar el primer y último corchete
        # Esto es menos robusto pero puede funcionar si el JSON está "suelto"
        try:
            start_brace = gemini_text_response.find('{')
            end_brace = gemini_text_response.rfind('}')
            if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                json_string = gemini_text_response[start_brace : end_brace + 1]
            else:
                json_string = gemini_text_response # Intentar con el texto completo si no se encuentra un bloque claro
        except Exception:
            json_string = gemini_text_response # Fallback

    try:
        parsed_data = json.loads(json_string)

        resultado = {
            'nivel_fiabilidad': parsed_data.get('nivel_fiabilidad', 'No se pudo determinar'),
            'resumen_evaluacion': parsed_data.get('resumen_evaluacion', 'No se pudo extraer el resumen.'),
            'fuentes_soporte': parsed_data.get('fuentes_soporte', []),
            'posibles_sesgos': parsed_data.get('posibles_sesgos', 'No se identificaron sesgos.'),
            'advertencias': parsed_data.get('advertencias', 'Ninguna.'),
            'respuesta_completa': gemini_text_response # Siempre guardar la respuesta cruda para depuración
        }
    except json.JSONDecodeError as e:
        # Si el parsing JSON falla incluso después de intentar limpiar
        resultado = {
            'nivel_fiabilidad': 'Error de Formato',
            'resumen_evaluacion': f'La IA no generó un JSON válido. Error: {e}. Respuesta cruda: {gemini_text_response}',
            'fuentes_soporte': [],
            'posibles_sesgos': '',
            'advertencias': '',
            'respuesta_completa': gemini_text_response
        }
    except Exception as e:
        # Otros errores inesperados durante el procesamiento
        resultado = {
            'nivel_fiabilidad': 'Error de Procesamiento',
            'resumen_evaluacion': f'Ocurrió un error inesperado al procesar la respuesta de la IA: {e}',
            'fuentes_soporte': [],
            'posibles_sesgos': '',
            'advertencias': '',
            'respuesta_completa': gemini_text_response
        }
    return resultado

def verificar_noticia_imagen(request):
    """Vista para la verificación de noticias solo con imagen (obligatoria)."""
    resultado = None
    if request.method == 'POST':
        form = ImageVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            imagen = form.cleaned_data['imagen'] # La imagen es ahora obligatoria

            # Prompt específico para la imagen
            # Le pedimos que analice la imagen como la fuente principal de información
            image_prompt_text = f"""Evalúa la fiabilidad de la información presente en la imagen proporcionada. Asume que la imagen contiene el contenido principal de la noticia. Responde exclusivamente en formato JSON, con las siguientes claves:

            "nivel_fiabilidad": (string, ej. "Alta", "Moderada", "Baja", "No se puede determinar")
            "resumen_evaluacion": (string, un breve resumen de tu análisis basado en la imagen)
            "fuentes_soporte": (array de strings, enlaces o descripciones de fuentes confiables que verifican/desmienten la información visible en la imagen, máximo 3-5)
            "posibles_sesgos": (string, si identificas algún sesgo o técnica de desinformación basada en la imagen, explica brevemente)
            "advertencias": (string, cualquier otra advertencia o consideración adicional sobre la imagen o su contenido)

            Considera los siguientes aspectos en tu análisis:
            - Contenido de la imagen: ¿Qué información visual y textual se presenta?
            - Veracidad de las afirmaciones visibles: ¿Son las afirmaciones fácticas precisas y están respaldadas por evidencia externa que puedas encontrar?
            - Credibilidad de la fuente visible (logos, URLs en la imagen): Si es legible.
            - Manipulación de imagen: ¿Hay indicios de que la imagen ha sido alterada o está fuera de contexto?
            - Relevancia y contexto: ¿Es la imagen relevante para el tema que parece abordar?

            Asegúrate de que la respuesta sea un JSON válido.
            """

            parts = [
                image_prompt_text,
                {'mime_type': imagen.content_type, 'data': imagen.read()}
            ]

            try:
                response = model_vision.generate_content(parts)
                gemini_text_response = response.text
                resultado = parse_gemini_response(gemini_text_response)

            except Exception as e:
                resultado = {'error': f"Ocurrió un error al comunicarse con la IA (imagen): {e}. Por favor, intente de nuevo más tarde."}
    else:
        form = ImageVerificationForm()

    return render(request, 'training_report/verificador_con_imagen.html', {'form': form, 'resultado': resultado})




def analizar_imagenes_comida(request, mensaje_prompt=None):
    resultado = None
    token_info = None
    form = ImagenForm(request.POST, request.FILES)

    if request.method == 'POST':
        if form.is_valid():
            imagenes_files = request.FILES.getlist('imagen')
            imagenes_data_to_send = []

            for imagen_file in imagenes_files:
                img_data_to_send = None
                try:
                    img = Image.open(imagen_file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    target_size = (250, 250)
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    mime_type = 'image/jpeg'
                    quality = 100
                    img.save(buffer, format="JPEG", quality=quality)
                    imagen_bytes = buffer.getvalue()
                    imagen_base64 = base64.b64encode(imagen_bytes).decode('utf-8')
                    img_data_to_send = {"mime_type": mime_type, "data": imagen_base64}
                    print(f"Imagen preprocesada: Tamaño max ~{target_size}px, Calidad JPEG ~{quality}")
                except Exception as e:
                    print(f"Error al procesar imagen con Pillow: {e}. Se usará la imagen original.")
                    imagen_file.seek(0)
                    imagen_base64_original = base64.b64encode(imagen_file.read()).decode('utf-8')
                    img_data_to_send = {"mime_type": imagen_file.content_type, "data": imagen_base64_original}

                imagenes_data_to_send.append(img_data_to_send)

            # --- Llamada a la API con la lista de imágenes ---
            if imagenes_data_to_send:
                prompt = (mensaje_prompt + " Solo responde con la información solicitada, nada más.") if mensaje_prompt else """
                Imagenes de comida sobrante da una respuesta de la siguiente forma para cada imagen:
                - Categoría (Carne, Pescado, carne o pescado en salsa, marisco)
                - Subcategoría
                - Información adicional del plato
                - Posibles ingredientes
                - Recomendaciones para recalentar y aprovechar las sobras
                Solo responde con la información solicitada, nada más.
                """
                model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=prompt)
                try:
                    response = model.generate_content(imagenes_data_to_send)
                    resultado = response.text
                    resultado = resultado.replace("```", " ")  # Eliminar bloques de código markdown
                    resultado = resultado.replace("json", " ")  # Eliminar la palabra 'json' si está presente
                    print("Tipo de variable: " + str(type(resultado)))
                    if hasattr(response, 'usage_metadata'):
                        token_info = {
                            'prompt_tokens': response.usage_metadata.prompt_token_count,
                            'response_tokens': response.usage_metadata.candidates_token_count,
                            'total_tokens': response.usage_metadata.total_token_count,
                        }
                        print("Tokens usados (con imágenes procesadas):", token_info)

                    # --- Export the prompt, response, and tokens to a TXT file ---
                    data = {
                        "hour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "prompt": prompt,
                        "response": resultado,
                        "tokens": token_info.get('total_tokens', 'N/A') if token_info else 'N/A'
                    }
                    export_to_txt(data, "analisis_proporcion_comida.txt", mode=1)

                    try:
                        json_response = json.loads(resultado)
                        
                        print(f"Successfully analyzed and saved AI info for images")
                        return json_response
                        
                    except json.JSONDecodeError as e:
                        print(f"Error parsing JSON response: {e}")
                        print(f"Raw response: {resultado}")
                        return None

                except Exception as e:
                    resultado = f"Error al llamar a la API de Gemini: {e}"
                    print(f"Error en Gemini API: {e}")
                    token_info = None
            else:
                resultado = "Error: No se pudieron preparar los datos de las imágenes."
    return render(request, 'training_report/crear_rueda_alimentos.html', {
        'form': form,
        'resultado': resultado,
        'token_info': token_info
    })

from django.http import JsonResponse

def analizar_imagenes_personalizado(request):
    mensaje_prompt = """Analiza estas imágenes de comida sobrante y proporciona la información en formato JSON con exactamente la siguiente estructura:
        {
            "imagenes": [
                {
                    "categoria": "Tipo de alimento (Carne, Pescado, Verdura, etc.)",
                    "subcategoria": "Especificación más detallada",
                    "descripcion": "Información adicional del plato",
                    "ingredientes": [
                        {
                            "nombre": "ingrediente1",
                            "proporcion": "estimación en Kg"
                        },
                        {
                            "nombre": "ingrediente2",
                            "proporcion": "estimación en Kg"
                        }
                    ],
                    "recomendaciones": "Sugerencias para aprovechar las sobras"
                }
            ]
        }
        """
    
    result = analizar_imagenes_comida(request, mensaje_prompt=mensaje_prompt)
    
    # Check if result is a dict or list (JSON data)
    if isinstance(result, (dict, list)):
        return JsonResponse(result, safe=False)
    else:
        # If it's not JSON data, it's likely already an HttpResponse from render()
        # In this case, just return it as is
        return result if result else render(request, 'training_report/crear_rueda_alimentos.html', {
            'form': ImagenForm(),
            'resultado': None,
            'token_info': None
        })

def crear_rueda_alimentos(request):
    resultado = None
    token_info = None
    
    if request.method == 'POST':
        consulta_texto = request.POST.get('consulta_texto', '')
        
        if consulta_texto:
            try:
                prompt = "A partir de la siguiente rueda de alimentos: " + consulta_texto + \
                """Crea un menu semanal para un buffet de hotel donde incluyas almuerzo y cena con mínimo 3 platos principales y 3 entrantes.
                La rueda de alimentos debe ser variada, equilibrada y sostenible, si hay elementos del lunes que se pueden reaprovechar para otro día mejor.
                Señala las comidas que se pueden reaprovechar de otros días en el menu.
                Tener en cuenta si nombran alimentos que mas se suelen desperdiciar para consejos de reaprovechamiento."""
                
                # Llamada a la API 
                model = genai.GenerativeModel('gemini-2.0-flash', 
                                             system_instruction="Solo responde con la información solicitada, nada más.")
                
                response = model.generate_content(prompt)
                resultado = response.text
                
                # Recopilación de información sobre tokens 
                if hasattr(response, 'usage_metadata'):
                    token_info = {
                        'prompt_tokens': response.usage_metadata.prompt_token_count,
                        'response_tokens': response.usage_metadata.candidates_token_count,
                        'total_tokens': response.usage_metadata.total_token_count,
                    }
                    print("Tokens usados:", token_info) 

                data = {
                    "hour": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "prompt": prompt,
                    "response": resultado,
                    "tokens": token_info.get('total_tokens', 'N/A') if token_info else 'N/A'
                }
                export_to_txt(data, "ruedas_alimentos.txt", mode=1)
                
            except Exception as e:
                resultado = f"Error al llamar a la API de Gemini: {e}"
                print(f"Error en Gemini API: {e}")
                token_info = None
    
    return render(request, 'training_report/crear_rueda_alimentos.html', {
        'resultado': resultado,
        'token_info': token_info
    })

class AnalizarImagenesProporcionView(View):
    template_name = 'training_report/analizar_imagenes_proporciones.html'
    base_prompt = """De las siguientes imagenes de sobras de comida 
    ¿cual es la proporcion y peso de cada tipo de comida y de ingredientes que mas tiro? De manera aproximada"""

    def get(self, request, *args, **kwargs):
        # Render the form for GET requests
        form = ImagenForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        # Handle the POST request
        form = ImagenForm(request.POST, request.FILES)
        peso = request.POST.get('peso', None)  # Get the weight from the form

        if form.is_valid() and peso:
            try:
                # Append the weight to the prompt
                mensaje_prompt = f"{self.base_prompt}. El peso total de la comida es {peso} kg incluyendo todos los alimentos que se encuentran en la imagen."

                # Call the analizar_imagenes_comida logic
                return analizar_imagenes_comida(request, mensaje_prompt=mensaje_prompt)
            except Exception as e:
                return render(request, self.template_name, {'form': form, 'error': str(e)})
        else:
            return render(request, self.template_name, {'form': form, 'error': 'Por favor, introduce un peso válido.'})