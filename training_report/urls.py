from django.urls import path, include
from .views import TrainingReportListView, TrainingReportCreate, TrainingReportUpdate, TrainingReportDelete, create_training, sign_training, generate_pdf, final_training_view, send_email, analizar_imagenes_comida, analizar_imagenes_personalizado, crear_rueda_alimentos, verificar_noticia, verificar_noticia_imagen
from .views import AnalizarImagenesProporcionView

TrainingReports_patterns = ([ 
    path('', TrainingReportListView.as_view(), name='training_report'),
    path('create/', TrainingReportCreate.as_view(), name='create'),
    path('update/<int:pk>/', TrainingReportUpdate.as_view(), name='update'),
    path('delete/<int:pk>/', TrainingReportDelete.as_view(), name='delete'),
    path('create_training/', create_training, name='create_training'),
    path('sign_training/<int:training_id>/', sign_training, name='sign_training'),
    path('generate_pdf/<int:training_id>/', generate_pdf, name='generate_pdf'),
    path('final_training/<int:training_id>/', final_training_view, name='final_training'),
    path('<int:training_id>/', send_email, name='send_email'),
    path('analizar_comida/', analizar_imagenes_comida, name='analizar_comida'),
    path('analizar_imagenes_personalizado/', analizar_imagenes_personalizado, name='analizar_imagenes_personalizado'),
    path('analizar-imagenes-proporcion/', AnalizarImagenesProporcionView.as_view(), name='analizar_imagenes_proporcion'),
    path('crear-rueda-alimentos/', crear_rueda_alimentos, name='crear_rueda_alimentos'),
    path('verificar/', verificar_noticia, name='verificar_noticia'),
    path('verificar-imagen/', verificar_noticia_imagen, name='verificar_noticia_imagen'),

], 'training_report')

urlpatterns = [
    path('training_report/', include(TrainingReports_patterns)),    
]