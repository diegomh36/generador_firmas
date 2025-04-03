from django import template
from training_report.models import TrainingReport

register = template.Library()

@register.simple_tag
def get_training_report_list():
    training_reports = TrainingReport.objects.all()
    return training_reports