from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User

class Content(models.Model):
    name = models.CharField(verbose_name="Nombre del contenido", max_length=200)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated = models.DateTimeField(auto_now=True, verbose_name="Fecha de edición")

    class Meta:
        verbose_name = "contenido"
        verbose_name_plural = "contenidos"
        ordering = ['-created', ]

    def __str__(self):
        return self.name

class TrainingReport(models.Model):
    name = models.CharField(verbose_name="Nombre de formador/a", max_length=200)
    assistants = models.SmallIntegerField(verbose_name="Número de asistentes", default=1, 
                                          validators=[MinValueValidator(1), MaxValueValidator(20)])
    date = models.DateTimeField(verbose_name="Fecha de formación")
    author = models.ForeignKey(User, verbose_name="Autor", on_delete=models.PROTECT, null=True, blank=True)
    contents = models.ManyToManyField(Content, verbose_name="Contenido de formación")
    sign_all = models.CharField(max_length=3,choices=[("one", "Solo la persona responsable"), ("all", "Cada participante")], default="all", verbose_name="Personas a firmar")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated = models.DateTimeField(auto_now=True, verbose_name="Fecha de edición")

    class Meta:
        verbose_name = "parte de formación"
        verbose_name_plural = "partes de formación"
        ordering = ['date', ]

    def __str__(self):
        return self.name

class Signature(models.Model):
    training = models.ForeignKey(TrainingReport, on_delete=models.CASCADE)
    signer_name = models.CharField(max_length=200)
    signature_image = models.TextField(null=True, blank=True)  # Base64 de la firma

    def __str__(self):
        return f"Firma de {self.signer_name} en {self.training.name}"