from django.conf import settings
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            student_name=settings.STUDENT_NAME,
            student_section=settings.STUDENT_SECTION,
            student_year=settings.STUDENT_YEAR,
        )
        return context
