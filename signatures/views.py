from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Page, Content
from .forms import PageForm
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
import os
from django.shortcuts import render
from django.conf import settings
from reportlab.lib import colors
from datetime import datetime
import locale
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

class StaffRequiredMixin(object):
    """
    Este mixin requiere que el usuario sea miembro del staff
    """
    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super(StaffRequiredMixin, self).dispatch(request, *args, **kwargs)

locale.setlocale(locale.LC_TIME, 'es_ES')
# Create your views here.

@method_decorator(staff_member_required, name='dispatch')
class PageListView(ListView):
    model = Page

@method_decorator(staff_member_required, name='dispatch')
class PageDetailView(DetailView):
    model = Page

@method_decorator(staff_member_required, name='dispatch')
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
        ruta_logo = os.path.join(settings.BASE_DIR, "pages\static\pages\img\logo.png")
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