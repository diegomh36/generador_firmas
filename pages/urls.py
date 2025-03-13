from django.urls import path
from .views import PageListView, PageDetailView, PageCreate, PageUpdate, PageDelete, generar_pdf, create_training, sign_training, generate_pdf, finalizar_view, enviar_pdf_email, enviar_pdf, firmar_documento,sign_training2

pages_patterns = ([
    path('', PageListView.as_view(), name='pages'),
    path('<int:pk>/<slug:slug>/', PageDetailView.as_view(), name='page'),
    path('create/', PageCreate.as_view(), name='create'),
    path('update/<int:pk>/', PageUpdate.as_view(), name='update'),
    path('delete/<int:pk>/', PageDelete.as_view(), name='delete'),
    path('generar-pdf/', generar_pdf, name='generar_pdf'),
    path('crear-parte/', create_training, name='crear_parte'),  
    path('firmar/<int:page_id>/<str:sign_all>/', sign_training, name='firmar'),
    path('firmar2/<int:page_id>/<str:sign_all>/', sign_training2, name='firmar2'),   
    path('descargar-pdf/<int:page_id>/', generate_pdf, name='descargar_pdf'),
    path('finalizar/<int:page_id>/', finalizar_view, name='finalizar'),
    path('documento/<int:page_id>/enviar-email/', enviar_pdf_email, name='enviar_pdf_email'),
    path('enviar/<int:page_id>/', enviar_pdf, name='enviar_pdf'),
    path('firmar_documento/<int:page_id>/', firmar_documento, name='firmar_documento'),
], 'pages')