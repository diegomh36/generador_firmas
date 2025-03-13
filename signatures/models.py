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

class Page(models.Model):#Cambiar nombre a SignatureDoc, al campo de Json llamarlo Data
    name = models.CharField(verbose_name="Nombre de formador/a", max_length=200)
    assistants = models.SmallIntegerField(verbose_name="Número de asistentes", default=1, 
                                          validators=[MinValueValidator(1), MaxValueValidator(20)])
    date = models.DateField(verbose_name="Fecha de formación")
    author = models.ForeignKey(User, verbose_name="Autor", on_delete=models.PROTECT, null=True, blank=True)
    contents = models.ManyToManyField(Content, verbose_name="Contenido de formación")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated = models.DateTimeField(auto_now=True, verbose_name="Fecha de edición")

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ['date', ]

    def __str__(self):
        return self.name