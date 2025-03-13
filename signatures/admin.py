from django.contrib import admin
from .models import Page, Content

# Register your models here.

class ContentAdmin(admin.ModelAdmin):
    readonly_fields = ('created', 'updated')
    list_display = ('name',)

class PageAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'date', 'post_contents',)
    ordering = ('name', 'date',)
    search_fields = ('name', 'author__username', 'contents__name')
    date_hierarchy = 'date'
    list_filter = ('author__username',)

    def post_contents(self, obj):
        return ", ".join([c.name for c in obj.contents.all().order_by("name")])
    post_contents.short_description = "Contenidos"

admin.site.register(Content, ContentAdmin)
admin.site.register(Page, PageAdmin)