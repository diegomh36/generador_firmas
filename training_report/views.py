import base64
from io import BytesIO
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import TrainingReport, Content, Signature
from .forms import TrainingReportForm, ImagenForm
from reportlab.pdfgen import canvas
from django.http import HttpResponse
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

with open("token.config", "r") as token_file:
    api_key = token_file.read().strip()
    
genai.configure(api_key=api_key)

def analizar_imagen_comida(request):
    resultado = None
    token_info = None
    form = ImagenForm()

    if request.method == 'POST':
        form = ImagenForm(request.POST, request.FILES)
        if form.is_valid():
            imagen_file = request.FILES['imagen']
            img_data_to_send = None # Variable para guardar los datos de imagen procesados

            # --- Inicio: Preprocesamiento de Imagen con Pillow ---
            try:
                img = Image.open(imagen_file)

                # Opcional: Convertir a RGB si es RGBA o Paleta (necesario para JPEG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # --- Redimensionar la Imagen ---
                # Ajustar el tamaño de la imagen si es necesario para ahorrar tokens
                target_size = (250, 250)
                img.thumbnail(target_size, Image.Resampling.LANCZOS) 

                # --- Guardar en un buffer en memoria (formato JPEG con calidad ajustable) ---
                buffer = io.BytesIO()
                mime_type = 'image/jpeg'
                # Ajustar la calidad si es necesario para ahorrar tokens
                quality = 100
                img.save(buffer, format="JPEG", quality=quality)

                # Obtener los bytes y codificar en Base64
                imagen_bytes = buffer.getvalue()
                imagen_base64 = base64.b64encode(imagen_bytes).decode('utf-8')

                img_data_to_send = {"mime_type": mime_type, "data": imagen_base64}
                print(f"Imagen preprocesada: Tamaño max ~{target_size}px, Calidad JPEG ~{quality}")

            except Exception as e:
                print(f"Error al procesar imagen con Pillow: {e}. Se usará la imagen original.")
                # Fallback: Si falla el procesamiento, usa la imagen original
                imagen_file.seek(0) # Importante resetear el puntero del archivo
                imagen_base64_original = base64.b64encode(imagen_file.read()).decode('utf-8')
                img_data_to_send = {"mime_type": imagen_file.content_type, "data": imagen_base64_original}
            # --- Fin: Preprocesamiento de Imagen ---


            # --- Llamada a la API con la imagen (posiblemente) procesada ---
            if img_data_to_send:
                # Define el prompt que actuará como instrucción del sistema
                system_prompt = """
                A partir de la imagen de comida sobrante solo di:
                - Categoría (Carne, Pescado, carne o pescado en salsa, marisco)
                - Subcategoría
                - Información adicional del plato
                - Posibles ingredientes
                - Recomendaciones para recalentar y aprovechar las sobras
                """
                # Inicializa el modelo con la instrucción del sistema
                model = genai.GenerativeModel(
                    'gemini-2.0-flash', 
                    system_instruction=system_prompt
                )

                # Envía SOLO la imagen (procesada o la original si hubo error)
                try:
                    response = model.generate_content([img_data_to_send]) # <--- USA LA IMAGEN PROCESADA
                    resultado = response.text

                    # Obtener información de tokens
                    if hasattr(response, 'usage_metadata'):
                        token_info = {
                            'prompt_tokens': response.usage_metadata.prompt_token_count,
                            'response_tokens': response.usage_metadata.candidates_token_count,
                            'total_tokens': response.usage_metadata.total_token_count,
                        }
                        print("Tokens usados (con imagen procesada):", token_info)

                except Exception as e:
                    resultado = f"Error al llamar a la API de Gemini: {e}"
                    print(f"Error en Gemini API: {e}")
                    token_info = None
            else:
                # Esto solo ocurriría si img_data_to_send es None por alguna razón inesperada
                resultado = "Error: No se pudieron preparar los datos de la imagen."


    return render(request, 'training_report/analizar_imagen.html', {
        'form': form,
        'resultado': resultado,
        'token_info': token_info
    })

""" def analizar_imagenes_comidas(request):
    resultado = None
    token_info = None
    form = ImagenForm()

    if request.method == 'POST':
        form = ImagenForm(request.POST, request.FILES)
        if form.is_valid():
            model = genai.GenerativeModel('gemini-2.0-flash')
            

            # Procesar todas las imágenes subidas
            img_data_list = []
            for imagen_file in request.FILES.getlist('imagen'):  # Obtener lista de imágenes
                try:
                    img = Image.open(imagen_file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    target_size = (250, 250)
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=90)
                    imagen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    img_data_list.append({"mime_type": 'image/jpeg', "data": imagen_base64})
                except Exception as e:
                    print(f"Error procesando {imagen_file.name}: {e}")
                    # Fallback: imagen sin procesar
                    imagen_file.seek(0)
                    imagen_base64 = base64.b64encode(imagen_file.read()).decode('utf-8')
                    img_data_list.append({"mime_type": imagen_file.content_type, "data": imagen_base64})

            # Llamada a Gemini con TODAS las imágenes
            if img_data_list:
                try:
                    # Combina el prompt y las imágenes en un solo mensaje
                    response = model.generate_content([prompt] + img_data_list)
                    resultado = response.text

                    # Opcional: Mostrar tokens usados
                    if hasattr(response, 'usage_metadata'):
                        token_info = {
                            'total_tokens': response.usage_metadata.total_token_count,
                            'imagenes': len(img_data_list)
                        }
                except Exception as e:
                    resultado = f"Error en Gemini: {str(e)}"
            else:
                resultado = "No se subieron imágenes válidas."

    return render(request, 'training_report/analizar_imagenes.html', {
        'form': form,
        'resultado': resultado,
        'token_info': token_info
    }) """